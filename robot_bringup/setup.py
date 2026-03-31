from setuptools import setup

package_name = 'robot_bringup'

setup(
    name=package_name,
    version='0.0.1',
    packages=[],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/bringup.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='jnu',
    maintainer_email='jnu@example.com',
    description='Bringup placeholder package.',
    license='MIT',
)
