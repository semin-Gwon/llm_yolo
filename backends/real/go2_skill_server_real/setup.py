from setuptools import find_packages, setup

package_name = 'go2_skill_server_real'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='jnu',
    maintainer_email='jnu@example.com',
    description='Real backend skill action servers for llm_yolo MVP.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'navigate_to_pose_server = go2_skill_server_real.navigate_to_pose_server:main',
            'rotate_in_place_server = go2_skill_server_real.rotate_in_place_server:main',
            'scan_scene_server = go2_skill_server_real.scan_scene_server:main',
        ],
    },
)
