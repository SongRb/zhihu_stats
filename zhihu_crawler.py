import lucene, sys, os, threading, time, traceback
from java.io import File
from org.apache.lucene.analysis.core import WhitespaceAnalyzer
from org.apache.lucene.document import Document, Field, FieldType, StringField, TextField
from org.apache.lucene.index import DirectoryReader, FieldInfo, IndexWriter, IndexWriterConfig, Term
from org.apache.lucene.queryparser.classic import QueryParser
from org.apache.lucene.store import SimpleFSDirectory
from org.apache.lucene.search import MatchAllDocsQuery, IndexSearcher, Sort, SortField
from org.apache.lucene.util import Version
from zhihu_settings import *
from zhihu_common import *
import zhihu_index_and_task_dispatch as zh_iatd
import zhihu_client_api as zh_clnapi
import zhihu_page_analyzer as zh_pganlz

_stop = False

STOP_INDICATOR = '.~stop'

def check_stop_loop():
	global _stop

	os.remove(STOP_INDICATOR)
	while True:
		if os.path.exists(STOP_INDICATOR):
			_stop = True
			break
		time.sleep(1)

class task:
	def __init__(self):
		self.func_name = ''
		self.isint = True
		self.p_id = 0
		self.p_start = 0
		self.p_pagesize = 0
		self.p_extra = 0
		self.fails = 0
		self.finish_time = -1
		self.docid = 0

	def to_crawler_task(self):
		if self.isint:
			idval = int(self.p_id)
		else:
			idval = self.p_id
		res = zh_iatd.crawler_task(
			vars(zh_iatd)['get_and_parse_' + self.func_name],
			idval,
			self.p_start,
			self.p_pagesize,
			self.p_extra
		)
		res.fail_count = self.fails
		return res
	def from_crawler_task(self, ct):
		self.func_name = ct.func.func_name[14:]
		self.isint = isinstance(ct.prm_id, (int, long))
		self.p_id = str(ct.prm_id)
		self.p_start = ct.prm_start
		self.p_pagesize = ct.prm_pagesize
		self.p_extra = ct.prm_extra
		self.fails = ct.fail_count

	def to_document(self):
		def bool_to_int(bv):
			if bv:
				return 1
			return 0
		doc = Document()
		doc.add(StringField('func_name', self.func_name, Field.Store.YES))
		doc.add(StringField('isint', str(bool_to_int(self.isint)), Field.Store.YES))
		doc.add(StringField('id', self.p_id, Field.Store.YES))
		doc.add(StringField('start', str(self.p_start), Field.Store.YES))
		doc.add(StringField('pagesize', str(self.p_pagesize), Field.Store.YES))
		doc.add(StringField('pextra', str(self.p_extra), Field.Store.YES))
		doc.add(StringField('fails', str(self.fails), Field.Store.YES))
		doc.add(StringField('finish_time', str(self.finish_time), Field.Store.YES))
		doc.add(StringField('docid', str(self.docid), Field.Store.YES))
		return doc
	def from_document(self, doc):
		self.func_name = doc['func_name']
		self.isint = (doc['isint'] == '1')
		self.p_id = doc['id']
		self.p_start = int(doc['start'])
		self.p_pagesize = int(doc['pagesize'])
		self.p_extra = int(doc['pextra'])
		self.fails = int(doc['fails'])
		self.finish_time = int(doc['finish_time'])
		self.docid = long(doc['docid'])

def initialize(usr):
	task_writer = zh_iatd.create_index_writer(TASK_FOLDER)
	it = task()
	it.from_crawler_task(zh_iatd.crawler_task(zh_iatd.get_and_parse_user_data, usr))
	task_writer.addDocument(it.to_document())
	task_writer.commit()
	task_writer.close()

	db_writer = zh_iatd.create_index_writer()
	usrobj = zh_pganlz.user(usr)
	db_writer.addDocument(zh_pganlz.obj_to_document(usrobj))
	db_writer.commit()
	db_writer.close()

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

	haltt = threading.Thread(target = check_stop_loop)
	haltt.daemon = True
	haltt.start()

	db_writer = zh_iatd.create_index_writer()

	info_logger = external_console_logger('/tmp/zh_c_info')
	error_logger = external_console_logger('/tmp/zh_c_err')
	default_sorter = Sort(SortField('finish_time', SortField.Type.INT))
	default_query = MatchAllDocsQuery()

	while not _stop:
		task_reader = zh_iatd.create_searcher(TASK_FOLDER)
		searchres = task_reader.searcher.search(default_query, 100, default_sorter)
		idstart = searchres.totalHits
		resdocs = [task_reader.searcher.doc(x.doc) for x in searchres.scoreDocs]
		task_reader.close()

		task_writer = zh_iatd.create_index_writer(TASK_FOLDER)
		for doct in resdocs:
			curt = task()
			curt.from_document(doct)
			crlt = curt.to_crawler_task()
			try:
				crlt.func(session, crlt)
			except Exception as e:
				info_logger.write('FAIL')
				zh_pganlz.print_object(crlt, out = error_logger)
				error_logger.write(traceback.format_exc() + '\n')

				task_writer.deleteDocuments(Term('docid', str(doct['docid'])))
				curt.fails += 1
				task_writer.addDocument(curt.to_document())
			else:
				if not crlt.result_rep_obj is None:
					db_writer.deleteDocuments(crlt.result_query)
					db_writer.addDocument(zh_pganlz.obj_to_document(crlt.result_rep_obj))
				for x in crlt.result_new:
					db_writer.addDocument(zh_pganlz.obj_to_document(x))
				db_writer.commit()

				task_writer.deleteDocuments(Term('docid', str(doct['docid'])))
				curt.finish_time = int(time.time())
				task_writer.addDocument(curt.to_document())
				for x in crlt.result_tasks:
					newt = task()
					newt.from_crawler_task(x)
					newt.timestamp = idstart
					idstart += 1
					task_writer.addDocument(newt.to_document())
			info_logger.write(' +{0} -{1} {2}({3})\n'.format(len(crlt.result_tasks), curt.fails, crlt.func.func_name, crlt.prm_id))

			if _stop:
				break
		task_writer.commit()
		task_writer.close()

if __name__ == '__main__':
	main()
