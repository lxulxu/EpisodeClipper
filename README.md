# CharacterClipper
一个自动化砍柴脚本解放剪刀手，截取多个视频中指定人物片段，项目基于Python3.8 64-bit。

## 如何使用

### 1. 安装ffmpeg
<https://ffmpeg.org/download.html>下载，解压文件，将文件夹下的`bin`文件夹路径添加进环境变量。

### 2. 安装依赖
`pip install -r requirements.txt`

### 3. 安装模型
以下两种方法任选其一。
- 直接运行程序，模型自动下载
- <https://github.com/serengil/deepface_models/releases>下载`facenet512_weights.h5`，放入`.deepface/weights`文件夹

### 4. 准备数据
- `character`: 为每个角色新建文件夹，每个角色对应文件夹下存放 2 张以上单人人脸图像，建议 10 张左右，**文件夹和图像名称不要有中文字符**
- `video`: 存放MP4/MKV格式待剪辑视频，**建议视频名称不要有中文字符，否则视频会被重命名，中文字符替换为拼音**

## 函数调用示例
```python
if __name__ == '__main__':
  clip = CharacterClipper(start_time='00:00:00', end_time='00:10:00')
  clip.clip_character()
```
- **参数说明**
  - `start_time`: 剪辑开始时间，默认视频开端，格式`hh:mm:ss`，可用于跳过片头曲
  - `end_time`: 剪辑结束时间，默认视频结尾，格式`hh:mm:ss`，可用于跳过片尾曲

- **输出**
  - 角色视频片段：`result/角色/视频名称/[...].mp4`
  - 视频片段场景截图：`result/角色/视频名称/scene/[...].jpg`
  - 时间节点文件：`result/角色/视频名称/scene_list.csv`

## 流程图
  ```mermaid
  graph LR
  TRAIN_DATA[角色人脸数据集] --> RECOGNIZE
  SCENE[场景分割] --> SCENE_IMG[保存场景片段某帧图像]
  SCENE_IMG --> RECOGNIZE[人脸识别搜索出现角色的场景]
  RECOGNIZE --> TIME_LIST[筛选对应的时间点]
  TIME_LIST --> SPLIT[分割视频]
  ```