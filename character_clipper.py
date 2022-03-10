import os
import shutil
import time
from collections import Counter
from typing import Tuple

import scenedetect
from deepface import DeepFace
from pypinyin import lazy_pinyin
from scenedetect import video_splitter

VIDEO_FOLDER = 'video'
DATA_PATH = 'character'
SCENE_PATH = 'scene'
RESULT_PATH = 'result'
CSV_FILE = 'scene_list.csv'

TIME_STEP = 60
FRAME_CNT = 2

class CharacterClipper():

  def __init__(self, start_time='00:00:00', end_time='END'):
    self.start_time = start_time
    self.end_time = end_time
    self.video_manager = None

  def rename_filename(self, root_path: str, filename: str) -> str:
    '''
    Replace the Chinese characters in the name of file under the directory with Pinyin.
    '''
    src_path = os.path.join(os.getcwd(), root_path, filename)
    name, suffix = filename.split('.')
    new_filename = ''.join(lazy_pinyin(name)) + '.' + suffix
    dst_path = os.path.join(os.getcwd(), root_path, new_filename)

    try:
      os.rename(src_path, dst_path)
    except Exception:
      print('rename %s fail.' % filename)
    
    return new_filename

  def clear_folder(self, path: str):
    '''
    Empty the folder.
    '''
    if os.path.exists(path):
      shutil.rmtree(path, ignore_errors=True)
    time.sleep(0.5)
    os.makedirs(path, exist_ok=True)
  
  def init_video_manager(self, video_path: str):
    '''
    Initialize VideoManager.
    '''
    self.video_manager = scenedetect.VideoManager([video_path])
    fps = self.video_manager.get_framerate()
    start = scenedetect.FrameTimecode(self.start_time, fps)
    
    if self.end_time == 'END':
      self.video_manager.set_duration(start_time=start)
    else:
      end = scenedetect.FrameTimecode(self.end_time, fps)
      self.video_manager.set_duration(start_time=start, end_time=end)

    self.video_manager.set_downscale_factor()

  def find_scenes(self, output_dir: str) -> Tuple[list, dict]:
    '''
    Detect scenes and save a set number of images from each scene.

    Param output_dir: Directory to ouput the images into.

    Returns: List of scenes and dict of the format {scene_num:[image_paths]}.
    '''
    scene_manager = scenedetect.SceneManager()
    scene_manager.add_detector(scenedetect.ContentDetector())
    scene_manager.detect_scenes(self.video_manager, show_progress=False)
    scene_list = scene_manager.get_scene_list()
    thumbnails = scenedetect.scene_manager.save_images(scene_list, self.video_manager, num_images=1, output_dir=output_dir)

    return scene_list, thumbnails

  def recognize_face(self, img_path: str, data_path: str) -> list:
    '''
    Filter images from scenes that include specific character.

    Param img_path: Directory of scenes.

    Param data_path: Directory of input data.
    
    Returns: List of filenames of images that include the character.
    '''
    #rename training imgs if filenames have the Chinese characters
    datas = []
    for filename in os.listdir(data_path):
      filename = self.rename_filename(data_path, filename)
      filename = os.path.join(data_path, filename)
      datas.append(filename)

    #find imgs including the specific character
    filenames = []
    for data in datas:
      finds = DeepFace.find(data, img_path, enforce_detection=False, model_name='Facenet512')
      filenames += list(finds['identity'])
    
    #filter img list
    cnt_dict = Counter(filenames)
    character_imgs = [os.path.split(key)[1] for key, value in cnt_dict.items() if value > FRAME_CNT]

    return character_imgs
  
  def merge_scene_list(self, scene_list: list) -> list:
    '''
    Merge elements with a time difference of less than TIME_STEP between adjacent elements in the scene_list.
    '''
    if len(scene_list) == 0:
      return []
    
    merge_list = [scene_list[0]]

    for frame in scene_list:
      end_frame = merge_list[-1]
      if frame[0].get_seconds() - end_frame[1].get_seconds() > TIME_STEP:
        merge_list.append(frame)
      else:   
        merge_list[-1] = (end_frame[0], frame[1])

    return merge_list

  def filter_scene_list(self, ep_folder: str, character_data: str, scene_list: list, thumbnails: dict) -> list:
    '''
    Filter elements from scene_list that include specific character.

    Param ep_folder: Directory of the episode under the directory of the character.

    Param charater_data: Directory of the character images.

    Param scene_list:

    Param thumbnails: Dict of the format {scene_num:[image_paths]}.

    Returns: List of scenes.
    '''
    #generate scene list
    character_imgs = self.recognize_face(SCENE_PATH, character_data)

    for i, img_path in thumbnails.items():
      if img_path[0] not in character_imgs:
        scene_list[i] = None
    
    scene_list = [i for i in scene_list if i != None]
    scene_list = self.merge_scene_list(scene_list)
    
    if scene_list == []:
      return []
    
    self.clear_folder(ep_folder)

    #save scene imgs
    scene_dir = os.path.join(ep_folder, SCENE_PATH)
    self.clear_folder(scene_dir)
    scenedetect.scene_manager.save_images(scene_list, self.video_manager, num_images=1, output_dir=scene_dir)

    #save scene list as csv file
    with open(os.path.join(ep_folder, CSV_FILE), 'w') as f:
      scenedetect.scene_manager.write_scene_list(f, scene_list)

    return scene_list

  def split_video(self, videoname: str):
    '''
    Clip characters from the video.
    '''
    #init video_manager
    video_path = os.path.join(VIDEO_FOLDER, videoname)
    self.init_video_manager(video_path)
    self.video_manager.start()

    #split video to scenes
    self.clear_folder(SCENE_PATH)
    scene_list, thumbnails = self.find_scenes(SCENE_PATH)

    ep_name = videoname.split('.')[0]
    character_names = os.listdir(DATA_PATH)

    for charater in character_names:
      ep_folder = os.path.join(RESULT_PATH, charater, ep_name)
      charater_scene_list = scene_list[:]
      charater_scene_list = self.filter_scene_list(ep_folder, os.path.join(DATA_PATH, charater), charater_scene_list, thumbnails)
      if charater_scene_list != []:
        output_videoname = os.path.join(ep_folder, '$VIDEO_NAME-Scene$SCENE_NUMBER.mp4')
        video_splitter.split_video_ffmpeg([video_path], charater_scene_list, output_videoname, videoname)

    self.video_manager.release()
    
  def clip_character(self):
    '''
    Clip characters from all videos.
    '''
    dirs = [RESULT_PATH] + [os.path.join(RESULT_PATH, i) for i in os.listdir(DATA_PATH)]
    for path in dirs:
      if not os.path.exists(path):
        os.makedirs(path)
    
    videonames = os.listdir(VIDEO_FOLDER)
    #transform Chinese characters to pinyin
    videonames = [self.rename_filename(VIDEO_FOLDER, name) for name in videonames]

    for filename in videonames:
      t1 = time.time()
      self.split_video(filename)
      t2 = time.time()
      m, s = divmod(t2 - t1, 60)
      h, m = divmod(m, 60)
      print('%s uses %02d:%02d:%02d s.' % (filename, h, m, s))

    if os.path.exists(SCENE_PATH):
      shutil.rmtree(SCENE_PATH, ignore_errors=True)
  
if __name__ == '__main__':
  clip = CharacterClipper(start_time='00:00:00', end_time='00:10:00')
  #clip = CharacterClipper()
  clip.clip_character()