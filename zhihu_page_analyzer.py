import lucene, sys, re, bs4
from org.apache.lucene.document import Document, Field, FieldType, StringField, TextField
from zhihu_settings import *

_vm = lucene.initVM(vmargs = ['-Djava.awt.headless=true'])

def clean_soup(soup):
	for x in soup.find_all(re.compile('^(script|noscript|style|object)$', re.IGNORECASE)):
		x.decompose()
def remove_edit_buttons(soup):
	for x in soup.select('.zu-edit-button'):
		x.decompose()

class hyper_text:
	def __init__(self, node = None):
		self.set(node)

	def set(self, node):
		if node is None:
			self.raw = u''
			self.text = u''
		else:
			self.raw = unicode(node)
			alltext = bs4.BeautifulSoup(self.raw, HTML_PARSER)
			clean_soup(alltext)
			self.text = ' '.join(list(alltext.stripped_strings))

	def as_soup(self):
		return bs4.BeautifulSoup(self.raw, HTML_PARSER)

LT_NONE = 'N'
LT_LIST = 'L'
LT_INTLIST = 'O'
LT_STRING = 'S'
LT_FOR_QUERY = 'Q'
LT_HYPERTEXT = 'H'
LT_INT = 'I'
LT_BOOL = 'B'

def obj_to_document(obj):
	res = Document()
	res.add(StringField('index', str(obj.index), Field.Store.YES))
	res.add(StringField('type', obj.__class__.__name__, Field.Store.YES))
	for k, v in vars(obj.data).items():
		# TODO cut the text
		if v is None:
			res.add(StringField(LT_NONE + k, '', Field.Store.NO))
		elif isinstance(v, list):
			if len(v) > 0 and isinstance(v[0], int):
				res.add(TextField(LT_INTLIST + k, ' '.join((str(x) for x in v)), Field.Store.YES))
			else:
				res.add(TextField(LT_LIST + k, ' '.join(v), Field.Store.YES))
		elif isinstance(v, str) or isinstance(v, unicode):
			res.add(StringField(LT_STRING + k, v, Field.Store.YES))
			res.add(TextField(LT_FOR_QUERY + k, v, Field.Store.NO))
		elif isinstance(v, hyper_text):
			res.add(StringField(LT_HYPERTEXT + k, v.raw, Field.Store.YES))
			res.add(TextField(LT_FOR_QUERY + k, v.text, Field.Store.NO))
		elif isinstance(v, bool):
			if v:
				vs = '1'
			else:
				vs = '0'
			res.add(StringField(LT_BOOL + k, vs, Field.Store.YES))
		elif isinstance(v, int) or isinstance(v, long):
			res.add(StringField(LT_INT + k, str(v), Field.Store.YES))
		else:
			raise Exception('unrecognized data type')
	return res
def document_to_obj(doc, obj):
	for field in list(doc.fields.toArray()):
		rf = Field.cast_(field)
		k, v = rf.name(), rf.stringValue()
		if k == 'type':
			pass
		elif k == 'index':
			if isinstance(obj, user):
				obj.index = v
			else:
				obj.index = int(v)
		else:
			if k[0] == LT_FOR_QUERY:
				pass
			elif k[0] == LT_NONE:
				setattr(obj.data, k[1:], None)
			elif k[0] == LT_LIST:
				setattr(obj.data, k[1:], v.split())
			elif k[0] == LT_INTLIST:
				setattr(obj.data, k[1:], [int(x) for x in v.split()])
			elif k[0] == LT_STRING:
				setattr(obj.data, k[1:], v)
			elif k[0] == LT_HYPERTEXT:
				setattr(obj.data, k[1:], hyper_text(v))
			elif k[0] == LT_BOOL:
				if v == '1':
					setattr(obj.data, k[1:], True)
				elif v == '0':
					setattr(obj.data, k[1:], False)
				else:
					raise Exception('invalid bool value')
			elif k[0] == LT_INT:
				setattr(obj.data, k[1:], int(v))
			else:
				raise Exception('unrecognized property: ' + k)

class user_data:
	def __init__(self):
		self.alias = None
		self.description = None
		self.followed_indices = None
		self.asked_questions = None
class user:
	def __init__(self):
		self.index = None
		self.data = user_data()

	def parse_personal_info_page(self, pg):
		soup = bs4.BeautifulSoup(pg, HTML_PARSER)
		headercontent = soup.select('#ProfileHeader .ProfileHeader-main .ProfileHeader-contentHead')[0]
		self.data.alias = ' '.join(list(headercontent.select('.ProfileHeader-name')[0].stripped_strings))
		desccand = headercontent.select('.ProfileHeader-headline')
		if len(desccand) > 0:
			self.data.description = ' '.join(list(desccand[0].stripped_strings))
		else:
			self.data.description = ' '.join(list(soup.select(
				'#ProfileHeader .ProfileHeader-main .ProfileHeader-contentBody .ProfileHeader-info'
			)[0].stripped_strings))

class topic_data:
	def __init__(self):
		self.text = None
		self.description = None
		self.child_tag_indices = None
		self.watched_indices = None
class topic:
	def __init__(self):
		self.index = 0
		self.data = topic_data()

	@staticmethod
	def _extract_index(tag):
		return int(tag['href'].split('/')[-1])

	@staticmethod
	def parse_for_indices(tag): # zm-tag-editor
		res = []
		for x in tag.select('.zm-item-tag'):
			res.append(topic._extract_index(x))
		return res

	def parse_info_page(self, tag):
		remove_edit_buttons(tag)
		self.data.text = ' '.join(list(tag.select('#zh-topic-title h1.zm-editable-content')[0].stripped_strings))
		desctag = tag.select('#zh-topic-desc')
		if len(desctag) > 0:
			self.data.description = ' '.join(list(desctag[0].stripped_strings))

class answer_data:
	def __init__(self):
		self.text = None
		self.author = None
		self.likes = None
		self.question_index = None
class answer:
	def __init__(self):
		self.index = 0
		self.data = answer_data()

	def parse(self, tag): # zm-item-answer
		remove_edit_buttons(tag)
		try:
			self.index = int(tag['data-aid']) # FIXME mysterious bug here
		except:
			print tag.attrs
			raise
		self.data.text = hyper_text(tag.select('.zm-item-rich-text > .zm-editable-content')[0])
		answerhead = tag.select('.answer-head')[0]
		self.data.likes = int(answerhead.select('[data-votecount]')[0]['data-votecount'])
		authortag = answerhead.select('.zm-item-answer-author-info')[0].select('.summary-wrapper .author-link-line a')
		if len(authortag) > 0:
			self.data.author = authortag[0]['href'].split('/')[-1]

class question_data:
	def __init__(self):
		self.title = None
		self.description = None
		self.tag_indices = None
		self.author_index = None
		self.watched_indices = None
class question:
	def __init__(self):
		self.index = 0
		self.data = question_data()

	def parse_page(self, pg):
		soup = bs4.BeautifulSoup(pg, HTML_PARSER)
		remove_edit_buttons(soup)
		self.index = int(soup.select('#zh-single-question-page')[0]['data-urltoken'])
		self.data.title = ' '.join(list(soup.select('#zh-question-title')[0].stripped_strings))
		desc = soup.select('#zh-question-detail > .zm-editable-content')
		if len(desc) > 0:
			desc = hyper_text(desc[0])
		else:
			desc = soup.select('#zh-question-detail > textarea.content')
			if len(desc) > 0:
				desc = hyper_text(desc[0].string)
			else:
				desc = None
		self.data.description = desc
		self.data.tag_indices = topic.parse_for_indices(soup.select('.zm-tag-editor')[0])
		return int(soup.select('#zh-question-detail')[0]['data-resourceid'])

ZH_CT_QUESTION = 0
ZH_CT_ANSWER = 1
ZH_CT_ARTICLE = 2

class comment_data:
	def __init__(self):
		self.text = None
		self.target = None
		self.target_type = None
		self.is_response = None
		self.response_to_index = None
		self.author_index = None
		self.likes = None
class comment:
	def __init__(self):
		self.index = None
		self.data = comment_data()

	def parse_question_comment(self, tag):
		self.index = int(tag['data-id'])
		desc = tag.select('.zm-comment-hd .desc')
		self.data.is_response = len(desc) > 0
		if self.data.is_response:
			if desc[0].previous_sibling.name == 'span':
				self.data.author_index = desc[0].previous_sibling.a['href'].split('/')[-1]
			if desc[0].next_sibling.name == 'span':
				self.data.response_to_index = desc[0].next_sibling.a['href'].split('/')[-1]
		else:
			authortag = tag.select('.zm-comment-hd a')
			if len(authortag) > 0:
				self.data.author_index = authortag[0]['href'].split('/')[-1]
		self.data.text = hyper_text(tag.select('.zm-comment-content')[0])
		self.data.likes = int(tag.select('.zm-comment-ft .like-num em')[0].string)

class article_data:
	def __init__(self):
		self.likes = None
		self.comments = None
class article:
	def __init__(self):
		self.index = None

def print_object(obj, depth = 0):
	def write_depth(depth):
		sys.stdout.write('    ' * depth)

	sys.stdout.write('<{0}>'.format(obj.__class__.__name__))
	if obj is None:
		sys.stdout.write('\n')
	elif isinstance(obj, str) or isinstance(obj, unicode):
		sys.stdout.write(u'[{0}] "{1}"\n'.format(len(obj), obj))
	elif isinstance(obj, list) or isinstance(obj, tuple):
		sys.stdout.write('[{0}] {{\n'.format(len(obj)))
		for x in obj:
			write_depth(depth + 1)
			print_object(x, depth + 1)
		write_depth(depth)
		sys.stdout.write('}\n')
	elif isinstance(obj, dict):
		sys.stdout.write(' {\n')
		for k, v in obj.items():
			write_depth(depth + 1)
			print_object(k, depth + 1)
			write_depth(depth + 1)
			sys.stdout.write(' ->\n')
			write_depth(depth + 2)
			print_object(v, depth + 2)
		write_depth(depth)
		sys.stdout.write('}\n')
	elif isinstance(obj, bs4.Tag):
		sys.stdout.write(str(obj) + '\n')
	elif isinstance(obj, hyper_text):
		sys.stdout.write(' ' + obj.text + '\n')
	elif obj.__class__.__name__ == 'function':
		sys.stdout.write(' ' + obj.func_name + '\n')
	else:
		try:
			props = vars(obj)
		except:
			sys.stdout.write(' {0}\n'.format(str(obj)))
		else:
			sys.stdout.write(' {\n')
			for k, v in props.items():
				write_depth(depth + 1)
				sys.stdout.write(k + ': ')
				print_object(v, depth + 1)
			write_depth(depth)
			sys.stdout.write('}\n')

def main():
	if len(sys.argv) < 2:
		print 'Usage:\t', sys.argv[0], '<html file>'
		return
	with open(sys.argv[1], 'r') as fin:
		x = fin.read()
	result = question()
	result.parse_page(x)
	print
	print_object(result)
	print
	print 'document:'
	print
	x = question()
	document_to_obj(obj_to_document(result), x)
	print_object(x)

if __name__ == '__main__':
	main()
