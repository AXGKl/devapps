{'2746a281b66ab2a49e64c5b97e5417fd': [{'cmd': {'cmd': 'poetry shell',
                                               'expect': False,
                                               'timeout': 2},
                                       'res': '$ poetry shell      \n'
                                              '/home/gk/miniconda3/envs/devapps_py3.7/lib/python3.7/site-packages/setuptools/command/install.py:37: '
                                              'SetuptoolsDeprecationWarning: '
                                              'setup.py install is deprecated. '
                                              'Use build and pip and other '
                                              'standards-based '
                                              'tools.                           \n'
                                              '  '
                                              'setuptools.SetuptoolsDeprecationWarning,                                      \n'
                                              'Virtual environment already '
                                              'activated: '
                                              '\x1b[34m/home/gk/miniconda3/envs/devapps_py3.7\x1b[39m   \n'
                                              '$'},
                                      {'cmd': 'ops -h',
                                       'res': '$ ops -h      \n'
                                              '\n'
                                              'Usage: ops ACTION '
                                              '[--flag[=value] ...]  \n'
                                              '\n'
                                              'Available Plugins:  \n'
                                              '    - '
                                              '\x1b[1m\x1b[32mcontainer_build\x1b[0m\x1b[39m\x1b[49m                   \n'
                                              '    - '
                                              '\x1b[1m\x1b[32mcontainer_pull\n'
                                              '\x1b[0m\x1b[39m\x1b[49m    - '
                                              '\x1b[1m\x1b[32mfs_build\x1b[0m\x1b[39m\x1b[49m      \n'
                                              '    - '
                                              '\x1b[1m\x1b[32mlife_cycle\x1b[0m\x1b[39m\x1b[49m    \n'
                                              '    - '
                                              '\x1b[1m\x1b[32mlog_view\x1b[0m\x1b[39m\x1b[49m      \n'
                                              '    - '
                                              '\x1b[1m\x1b[32mproject\x1b[0m\x1b[39m\x1b[49m       \n'
                                              '    - '
                                              '\x1b[1m\x1b[32mrun\x1b[0m\x1b[39m\x1b[49m           \n'
                                              '\n'
                                              'Help:               \n'
                                              '    ops <action> '
                                              '<-h|--helpfull> '
                                              '[match]                                        \n'
                                              '\n'
                                              'Note:               \n'
                                              '    - Action shortcuts '
                                              'understood, e.g. action '
                                              '"foo_bar_baz" = '
                                              'fbb              \n'
                                              '    - Plugins are taken on '
                                              'first found '
                                              'basis                                    \n'
                                              '    - Flags also have shortcut '
                                              'versions (e.g. -hf for '
                                              '--helpfull)               \n'
                                              '\n'
                                              'Example:            \n'
                                              '    ops container_build -hf log '
                                              '# all flags about logging'}]}