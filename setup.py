from setuptools import setup
import logging
import ranger_squad

try:
    import pypandoc
except ImportError:
    """
    Don't fail if pandoc or pypandoc are not installed.
    However, it is better to publish the package with
    a formatted README.
    """
    logging.warning("Warning: Missing pypandoc, which is used to format the README. Install pypandoc before publishing a new version.")
    pypandoc = None


def readme():
    with open('README.md', 'r') as f:
        readme_md = f.read()
        if pypandoc:
            readme_rst = pypandoc.convert(readme_md, 'rst', format='md')
            return readme_rst
        else:
            return readme_md

setup(
    name='ranger-squad',
    version=ranger_squad.__version__,
    author='Alexey Aksenov',
    author_email='ezh@ezh.msk.ru',
    packages=['ranger_squad'],
    url='https://github.com/ezh/ranger-squad',
    license='Apache 2.0',
    description='Make ranger a team player',
    long_description=readme(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'ranger_squad = ranger_squad.__main__:main'
        ]
    },
    install_requires=[
        'pyzmq'
    ]
)
