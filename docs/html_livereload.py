"""
Uses livereload to reload the Sphinx doc whenever
a doc file has been editting.

 - Refreshes every 1 second.
 - Has to be run from within /docs
"""
from livereload import Server, shell


def main():
    server = Server()
    delay = 1
    server.watch('**/*.rst', shell('make html'), delay=delay)
    server.watch('**/*.md', shell('make html'), delay=delay)
    server.watch('**/*.py', shell('make html'), delay=delay)
    server.watch('_static/*', shell('make html'), delay=delay)
    server.watch('_templates/*', shell('make html'), delay=delay)
    server.serve(root='_build/html')


if __name__ == '__main__':
    main()
