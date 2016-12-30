import lucene, web, os, json
from java.io import File
from org.apache.lucene.analysis.core import WhitespaceAnalyzer
from org.apache.lucene.index import DirectoryReader, Term
from org.apache.lucene.queryparser.classic import QueryParser
from org.apache.lucene.store import SimpleFSDirectory
from org.apache.lucene.search import IndexSearcher, BooleanQuery, TermQuery, BooleanClause, Sort, SortField
from org.apache.lucene.index import FieldInfo, IndexWriter, IndexWriterConfig
from org.apache.lucene.document import Field
from org.apache.lucene.util import Version
import zhihu_page_analyzer as zh_pganlz
import zhihu_index_and_task_dispatch as zh_iatd
from zhihu_common import *
from zhihu_settings import *

_SERVER_PREFIX = 'SS'
_SERVER_ANY_PREFIX = 'SA'

renderer = web.template.render('./templates/')

_vm = None

class SS_:
	def GET(self):
		return 'well, this is embarrassing'

class SS_search:
	def GET(self):
		def build_text_query(k, v):
			return QueryParser(k, WhitespaceAnalyzer()).parse(' '.join(jieba.lcut(v)))
		def build_anyterm_query(field, strv):
			res = BooleanQuery()
			for i in strv.split():
				res.add(TermQuery(Term(field, i)), BooleanClause.Occur.SHOULD)
			return res

		global _vm

		_vm.attachCurrentThread()

		user_data = web.input()

		searcher = zh_iatd.create_searcher()
		query = BooleanQuery()
		# TODO querying with inexistant term gives garbage results
		return_doc_size = 10
		sort_lists = []
		for k, v in user_data.items():
			if k in ('index', 'type', 'tag_indices', 'author_index'):
				query.add(build_anyterm_query(k, user_data[k]), BooleanClause.Occur.MUST)
			elif k in ('text', 'contents', 'title', 'description', 'alias'):
				query.add(build_text_query(k + zh_pganlz.LTPF_FOR_QUERY, user_data[k]), BooleanClause.Occur.MUST)
			elif k == 'raw':
				query.add(QueryParser('index', WhitespaceAnalyzer()).parse(user_data[k]), BooleanClause.Occur.MUST)
			elif k == 'pagelimit':
				return_doc_size = int(user_data[k])
			elif k == 'sort':
				for x in user_data['sort']:
					sort_type = SortField.Type.STRING
					if 'type' in x.keys():
						if x['type'] == 'int':
							sort_type = SortField.Type.INT
					reverse = False
					if 'reverse' in x.keys():
						reverse = x['reverse']
					sort_lists.append(SortField(x['key'], sort_type, reverse))
		if len(sort_lists) > 0:
			res = searcher.searcher.search(query, return_doc_size, Sort(*sort_lists))
		else:
			res = searcher.searcher.search(query, return_doc_size)
		reslst = []
		for x in res.scoreDocs:
			reslst.append(zh_pganlz.obj_to_json(zh_pganlz.document_to_obj(searcher.searcher.doc(x.doc))))
		return json.dumps({'total': res.totalHits, 'data': reslst})

def generate_url_list():
	res = []
	for k in globals().keys():
		if k.startswith(_SERVER_PREFIX):
			res.append(k[len(_SERVER_PREFIX):].replace('_', '/').lower())
			res.append(k)
		elif k.startswith(_SERVER_ANY_PREFIX):
			res.append(k[len(_SERVER_ANY_PREFIX):].replace('_', '/').lower() + '(.*)')
			res.append(k)
	return res

def main():
	global _vm
	_vm = lucene.initVM(vmargs = ['-Djava.awt.headless=true'])
	web.application(generate_url_list(), globals()).run()

if __name__ == '__main__':
	main()
