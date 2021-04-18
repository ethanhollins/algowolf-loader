import os
import sys
from distutils.core import setup
from distutils.extension import Extension
# from Cython.Build import cythonize
from Cython.Distutils import build_ext


def retrieveAllCythonFiles(path, ext_modules, name):
	for i in os.listdir(path):
		c_path = os.path.join(path, i)
		if os.path.isdir(c_path):
			ext_modules = retrieveAllCythonFiles(c_path, ext_modules, name + [i])
		elif c_path.endswith('.pyx'):
			print('.'.join(name + [i]))
			ext_modules.append(Extension('.'.join(name + [i.split('.')[0]]), [c_path]))
			# file_list.append(c_path)

	return ext_modules

# GET FILES
PATH = sys.argv[-1]
del sys.argv[-1]

os.chdir(PATH)
ext_modules = retrieveAllCythonFiles(PATH, [], [])

print(ext_modules)

# BUILD
# setup(ext_modules = cythonize(FILE_LIST))
setup(
	cmdclass = {'build_ext': build_ext},
	ext_modules = ext_modules,
    language='c++'
)

