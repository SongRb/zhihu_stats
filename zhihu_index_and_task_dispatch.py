import lucene, urllib2, bs4, collections, os, sys, time, traceback
from java.io import File
from org.apache.lucene.analysis.core import WhitespaceAnalyzer
from org.apache.lucene.index import DirectoryReader
from org.apache.lucene.queryparser.classic import QueryParser
from org.apache.lucene.store import SimpleFSDirectory
from org.apache.lucene.search import IndexSearcher, BooleanQuery, BooleanClause
from org.apache.lucene.index import FieldInfo, IndexWriter, IndexWriterConfig
from org.apache.lucene.util import Version
import zhihu_client_api as zh_clnapi
import zhihu_page_analyzer as zh_pganlz
from zhihu_settings import *

ZH_TGT_USERDATA = 0
ZH_TGT_USERFOLLOWER = 1
ZH_TGT_CHILDRENTOPIC = 2
ZH_TGT_QUESTIONWATCHER = 4
ZH_TGT_ASKED = 8
ZH_TGT_TOPICDATA = 9

ZH_TGT_QUESTION_DATA = 5
ZH_TGT_ANSWERS = 6
ZH_TGT_ARTICLE = 7
ZH_TGT_COMMENTOF = 0x80

ZH_ET_QUESTION = 0
ZH_ET_ANSWER = 1
ZH_ET_COMMENT = 2
ZH_ET_ARTICLE = 3
ZH_ET_USER = 4
ZH_ET_TOPIC = 5

class crawler_task:
	def __init__(self, func, p_id = 0, p_start = 0, p_pagesize = 0, p_extra = 0):
		self.func = func
		self.result = None
		self.replace = False
		self.result_tasks = []
		self.prm_id = p_id
		self.prm_start = p_start
		self.prm_pagesize = p_pagesize
		self.prm_extra = p_extra
		self.fail_count = 0

def create_index_writer():
	config = IndexWriterConfig(Version.LUCENE_CURRENT, WhitespaceAnalyzer())
	config.setOpenMode(IndexWriterConfig.OpenMode.CREATE_OR_APPEND)
	return IndexWriter(SimpleFSDirectory(File(INDEXED_FOLDER)), config)

class searcher_wrapper:
	def __init__(self, reader):
		self.reader = reader
		self.searcher = IndexSearcher(self.reader)
	def close(self):
		self.reader.close()
def create_searcher():
	return searcher_wrapper(DirectoryReader.open(SimpleFSDirectory(File(INDEXED_FOLDER))))
def create_query(qdict, analyzer):
	q = BooleanQuery()
	for k, v in qdict.items():
		q.add(QueryParser(k, analyzer).parse(v), BooleanClause.Occur.MUST)
	return q

def query_object(searcher, objid, objtype):
	analyzer = WhitespaceAnalyzer()
	query = create_query({'index': str(objid), 'type': objtype.__name__}, analyzer)
	res = searcher.searcher.search(query, 1)
	if res.totalHits == 0:
		return None
	obj = objtype()
	zh_pganlz.document_to_obj(searcher.searcher.doc(res.scoreDocs[0].doc), obj)
	return obj, query

def get_and_parse_question_data(session, tsk):
	tsk.result = zh_pganlz.question()
	resourceid = tsk.result.parse_page(session.opener.open(urllib2.Request(
		url = 'https://www.zhihu.com/question/{0}'.format(tsk.prm_id)
	)).read())
	# generate subtasks
	searcher = create_searcher()
	for x in tsk.result.data.tag_indices:
		if query_object(searcher, x, zh_pganlz.topic) is None:
			tsk.result_tasks.append(crawler_task(get_and_parse_topic_data, x))
	tsk.result_tasks.append(crawler_task(get_and_parse_answers, tsk.prm_id, 0, 10))
	tsk.result_tasks.append(crawler_task(get_and_parse_question_comment, tsk.prm_id, p_extra = resourceid))
	searcher.close()
def get_and_parse_answers(session, tsk):
	tsk.result = []
	ansjson = session.get_question_answer_list_raw(tsk.prm_id, tsk.prm_start, tsk.prm_pagesize)
	if len(ansjson['msg']) == 0:
		return
	for x in ansjson['msg']:
		ansobj = zh_pganlz.answer()
		ansobj.parse(bs4.BeautifulSoup(x, HTML_PARSER))
		ansobj.data.question_index = tsk.prm_id
		tsk.result.append(ansobj)
	# generate subtasks
	tsk.result_tasks.append(crawler_task(get_and_parse_answers, tsk.prm_id, tsk.prm_start + tsk.prm_pagesize, tsk.prm_pagesize))
	searcher = create_searcher()
	for x in tsk.result:
		if not x.data.author_index is None:
			if query_object(searcher, x.data.author_index, zh_pganlz.user) is None:
				tsk.result_tasks.append(crawler_task(get_and_parse_user_data, x.data.author_index))
		tsk.result_tasks.append(crawler_task(get_and_parse_answer_comment, x.index, 1))
	searcher.close()
def get_and_parse_user_data(session, tsk):
	tsk.result = zh_pganlz.user()
	tsk.result.index = tsk.prm_id
	tsk.result.parse_personal_info_page(session.opener.open(urllib2.Request(
		url = 'https://www.zhihu.com/people/{0}'.format(tsk.prm_id)
	)).read())
	# generate subtasks
	tsk.result_tasks.append(crawler_task(get_and_parse_user_followed, tsk.result.index, 0, 10))
	tsk.result_tasks.append(crawler_task(get_and_parse_user_asked, tsk.result.index, 0, 10))
def get_and_parse_user_followed(session, tsk):
	searcher = create_searcher()
	tsk.result = query_object(searcher, tsk.prm_id, zh_pganlz.user)
	tsk.replace = True
	foljson = session.get_followees_raw(tsk.prm_id, tsk.prm_start, tsk.prm_pagesize)
	newlst = []
	for userdata in foljson['data']:
		newlst.append(userdata['url_token'])
	if tsk.result[0].data.followed_indices is None:
		tsk.result[0].data.followed_indices = newlst
	else:
		tsk.result[0].data.followed_indices += newlst
	# generate subtasks
	for x in newlst:
		if query_object(searcher, x, zh_pganlz.user) is None:
			tsk.result_tasks.append(crawler_task(get_and_parse_user_data, x))
	searcher.close()
	if foljson['paging']['is_end']:
		return
	tsk.result_tasks.append(crawler_task(get_and_parse_user_followed, tsk.prm_id, tsk.prm_start + tsk.prm_pagesize, tsk.prm_pagesize))
def get_and_parse_user_asked(session, tsk):
	searcher = create_searcher()
	tsk.result = query_object(searcher, tsk.prm_id, zh_pganlz.user)
	tsk.replace = True
	askjson = session.get_asked_questions_raw(tsk.prm_id, tsk.prm_start, tsk.prm_pagesize)
	newlst = []
	for qdata in askjson['data']:
		newlst.append(qdata['id'])
	if tsk.result[0].data.asked_questions is None:
		tsk.result[0].data.asked_questions = newlst
	else:
		tsk.result[0].data.asked_questions += newlst
	# generate subtasks
	for x in newlst:
		if query_object(searcher, x, zh_pganlz.answer) is None:
			tsk.result_tasks.append(crawler_task(get_and_parse_question_data, x))
	searcher.close()
	if askjson['paging']['is_end']:
		return
	tsk.result_tasks.append(crawler_task(get_and_parse_user_asked, tsk.prm_id, tsk.prm_start + tsk.prm_pagesize, tsk.prm_pagesize))
def get_and_parse_topic_data(session, tsk):
	tsk.result = zh_pganlz.topic()
	tsk.result.parse_info_page(bs4.BeautifulSoup(session.opener.open(urllib2.Request(
		url = 'https://www.zhihu.com/topic/{0}/hot'.format(tsk.prm_id)
	)).read(), HTML_PARSER))
	# generate subtasks
	tsk.result_tasks.append(crawler_task(get_and_parse_topic_followers, tsk.result.index, 0, 10))
	tsk.result_tasks.append(crawler_task(get_and_parse_topic_children_indices, tsk.result.index, 0, 10))
def get_and_parse_question_comment(session, tsk):
	tsk.result = []
	soup = bs4.BeautifulSoup(session.get_question_comments_raw(tsk.prm_extra), HTML_PARSER)
	for x in soup.select('.zm-item-comment'):
		comm = zh_pganlz.comment()
		comm.parse_question_comment(x)
		comm.data.target = tsk.prm_id
		comm.data.target_type = zh_pganlz.ZH_CT_QUESTION
		tsk.result.append(comm)
	# generate subtasks
	searcher = create_searcher()
	for x in tsk.result:
		if not x.data.author_index is None:
			if query_object(searcher, x.data.author_index, zh_pganlz.user) is None:
				tsk.result_tasks.append(crawler_task(get_and_parse_user_data, x.data.author_index))
	searcher.close()
def get_and_parse_answer_comment(session, tsk):
	tsk.result = []
	commjson = session.get_answer_comments_raw(tsk.prm_id, tsk.prm_start)
	if len(commjson['data']) == 0:
		return
	for x in commjson['data']:
		comm = zh_pganlz.comment()
		comm.index = x['id']
		comm.data.target = tsk.prm_id
		comm.data.target_type = zh_pganlz.ZH_CT_ANSWER
		comm.data.likes = x['likesCount']
		comm.data.author_index = x['author']['slug']
		comm.data.response_to_index = x['inReplyToCommentId']
		comm.data.is_response = comm.data.response_to_index != 0
		if not comm.data.is_response:
			comm.data.response_to_index = None
		comm.data.text = x['content']
		tsk.result.append(comm)
	# generate subtasks
	searcher = create_searcher()
	for x in tsk.result:
		if not x.data.author_index is None:
			if query_object(searcher, x.data.author_index, zh_pganlz.user) is None:
				tsk.result_tasks.append(crawler_task(get_and_parse_user_data, x.data.author_index))
	tsk.result_tasks.append(crawler_task(get_and_parse_answer_comment, tsk.prm_id, tsk.prm_start + 1))
	searcher.close()
def get_and_parse_article_comment(session, tsk):
	tsk.result = []
def get_and_parse_topic_children_indices(session, tsk):
	tsk.result = None
def get_and_parse_topic_followers(session, tsk):
	tsk.result = None

def main():
	if os.path.exists('login_info'):
		with open('login_info', 'r') as fin:
			email = fin.readline()
			password = fin.readline()
		print 'Email:', email
		print 'Password: ', '*' * len(password)
	else:
		email = raw_input('Email: ')
		password = raw_input('Password: ')
	session = zh_clnapi.zhihu_session()
	session.login_email(email, password)

	q = collections.deque()
	q.append(crawler_task(get_and_parse_user_data, 'excited-vczh'))
	iwriter = create_index_writer()
	while len(q) > 0:
		ct = q.popleft()

		try:
			ct.func(session, ct)
		except Exception as e:
			print '! TASKFAIL'
			zh_pganlz.print_object(ct)
			traceback.print_exc()
			ct.result = None
			ct.result_tasks = []
			ct.fail_count += 1
			q.append(ct)
		else:
			if ct.replace:
				iwriter.deleteDocuments(ct.result[1])
				iwriter.addDocument(zh_pganlz.obj_to_document(ct.result[0]))
			elif isinstance(ct.result, list):
				for x in ct.result:
					iwriter.addDocument(zh_pganlz.obj_to_document(x))
			elif not ct.result is None:
				iwriter.addDocument(zh_pganlz.obj_to_document(ct.result))
			iwriter.commit()
			for x in ct.result_tasks:
				q.append(x)
			if ct.fail_count > 0:
				fstr = 'fails:{0} '.format(ct.fail_count)
			else:
				fstr = ''
			print 'TASKDONE', ct.func.func_name, ct.prm_id, fstr + 'tasks:{0}(+{1})'.format(len(q), len(ct.result_tasks))
		time.sleep(1)

if __name__ == '__main__':
	main()
