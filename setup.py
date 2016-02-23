import setuptools

setuptools.setup(
    name='dao.common',
    version='0.7.1',
    namespace_packages=['dao'],
    author='Sergii Kashaba',
    description='Deployment Automation and Orchestration Framework',
    classifiers=[
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English'
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries'
    ],
    packages=setuptools.find_packages(),
    install_requires=[
        'eventlet',
    ]
)
