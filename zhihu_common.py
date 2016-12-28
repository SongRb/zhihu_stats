import subprocess

def exec_in_new_console(cmd):
	return subprocess.Popen(('gnome-terminal', '-x') + cmd)

class external_console_logger:
	def __init__(self, logfile, mode = 'w'):
		self._file = open(logfile, mode)
		self._disp = exec_in_new_console(('tail', '-f', logfile))

	def write(self, s):
		self._file.write(s)
		self._file.flush()
