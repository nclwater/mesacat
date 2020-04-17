import subprocess
from distutils.dir_util import copy_tree
import os

subprocess.call([os.path.join('docs', 'make.bat'), 'html'])
copy_tree(os.path.join('docs', 'build', 'html'), 'docs')