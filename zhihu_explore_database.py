import lucene, urllib2, bs4, collections, os, sys, time, traceback
from java.io import File
from org.apache.lucene.analysis.core import WhitespaceAnalyzer
from org.apache.lucene.index import DirectoryReader
from org.apache.lucene.queryparser.classic import QueryParser
from org.apache.lucene.store import SimpleFSDirectory
from org.apache.lucene.search import IndexSearcher, BooleanQuery, BooleanClause, Sort, SortField
from org.apache.lucene.index import FieldInfo, IndexWriter, IndexWriterConfig
from org.apache.lucene.util import Version
import zhihu_page_analyzer as zh_pganlz

INDEXED_FOLDER = './.index/'

class doc_object_data:
	def __init__(self):
		pass
class doc_object:
	def __init__(self):
		self.index = None
		self.data = doc_object_data()

def main():
	searcher = IndexSearcher(DirectoryReader.open(SimpleFSDirectory(File(INDEXED_FOLDER))))
	analyzer = WhitespaceAnalyzer()
	query = BooleanQuery()
	query.add(QueryParser('type', analyzer).parse('answer'), BooleanClause.Occur.MUST)
	res = searcher.search(query, 100, Sort(SortField('Ilikes', SortField.Type.INT)))
	while True:
		for x in res.scoreDocs:
			doc = searcher.doc(x.doc)
			zh_pganlz.print_object(zh_pganlz.document_to_obj(doc))
			print
		res = searcher.searchAfter(res.scoreDocs[-1], query, 100, Sort(SortField('Ilikes', SortField.Type.INT)))
		raw_input('Press enter...')

if __name__ == '__main__':
	main()
