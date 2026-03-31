from setuptools import find_packages, setup

package_name = 'perception_node_real'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', ['config/real_perception_params.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='jnu',
    maintainer_email='jnu@example.com',
    description='Real perception node placeholder for llm_yolo MVP.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'perception_node = perception_node_real.perception_node:main',
        ],
    },
)
