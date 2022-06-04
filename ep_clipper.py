import ntpath
import os
import re
import shutil
import time
from collections import Counter
from typing import Tuple

import scenedetect
from deepface import DeepFace
from pypinyin import lazy_pinyin
from scenedetect import video_splitter

#data dirs
INPUT_PATH = 'input'
VIDEO_PATH = 'video'

#output dirs
BROLL_PATH = 'B-roll'
ROLE_PATH = 'role'
CLIP_PATH = 'clip'

#output file         
CSV_FILE = 'scene_list.csv'

#temp dirs
SCENE_PATH = 'scene'

ROLE_TIME_STEP = 60
BROLL_TIME_STEP = 2
FRAME_CNT = 2

class EpClipper():

  def __init__(self, start_time='00:00:00', end_time='END', modes=[0]):
    self.start_time = start_time
    self.end_time = end_time
    self.modes = modes
    self.video_manager = None

  def make_dirs(self):
    '''
    Prepare dirs.
    '''
    dirs = []
    if 0 in self.modes:
      dirs += [CLIP_PATH]
    if 1 in self.modes:
      dirs += [ROLE_PATH] + [os.path.join(ROLE_PATH, i) for i in os.listdir(INPUT_PATH)]    
    if 2 in self.modes:
      dirs += [BROLL_PATH]

    for path in dirs:
      if not os.path.exists(path):
        os.makedirs(path)

  def clear_folder(self, path: str):
    '''
    Empty the folder.
    '''
    if os.path.exists(path):
      shutil.rmtree(path, ignore_errors=True)
    time.sleep(0.5)
    os.makedirs(path, exist_ok=True)

  def rename_filename(self, root_path: str, filename: str) -> str:
    '''
    Replace names of files under the directory with Pinyin.
    '''
    src_path = os.path.join(os.getcwd(), root_path, filename)
    name, suffix = os.path.splitext(filename)
    new_filename = ''.join(lazy_pinyin(name)) + suffix
    dst_path = os.path.join(os.getcwd(), root_path, new_filename)

    try:
      os.rename(src_path, dst_path)
    except Exception:
      print('rename %s fail.' % filename)
    
    return new_filename

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

  def detect_scenes(self, output_dir: str) -> Tuple[list, dict]:
    '''
    Detect scenes and save a set number of images from each scene.

    Param output_dir: Directory to ouput the images.

    Returns: List of scenes and dict of the format {scene_num:[image_paths]}.
    '''
    scene_manager = scenedetect.SceneManager()

    #detect scenes
    scene_manager.add_detector(scenedetect.ContentDetector())
    scene_manager.detect_scenes(self.video_manager, show_progress=False)

    #save scene imgs
    scene_list = scene_manager.get_scene_list()
    thumbnails = scenedetect.scene_manager.save_images(scene_list, self.video_manager, num_images=1, output_dir=output_dir)

    return scene_list, thumbnails

  def recognize_role(self, input_path: str) -> list:
    '''
    Filter images from scenes that include specific role.
    '''
    #rename filenames if one of them has Chinese characters
    datas = []
    for filename in os.listdir(input_path):
      filename = self.rename_filename(input_path, filename)
      filename = os.path.join(input_path, filename)
      datas.append(filename)

    #find imgs including the specific role
    filenames = []
    for data in datas:
      finds = DeepFace.find(data, SCENE_PATH, enforce_detection=False, model_name='Facenet512', detector_backend='retinaface')
      filenames += list(finds['identity'])
    
    #filter img list
    cnt_dict = Counter(filenames)
    role_imgs = [os.path.split(key)[1] for key, value in cnt_dict.items() if value > FRAME_CNT]

    return role_imgs

  def detect_human(self, img: str) -> bool:
    '''
    Detect if there is human face in the image.
    '''
    try:
      _ = DeepFace.detectFace(os.path.join(SCENE_PATH, img), detector_backend='retinaface')
      return True
    except:
      return False

  def detect_broll(self) -> list:
    '''
    Filter images from scenes that do not include human face.
    '''
    img_names = os.listdir(SCENE_PATH)
    broll_imgs = [name for name in img_names if not self.detect_human(name)]

    return broll_imgs

  def filter_scene_list(self, scene_list: list, target_ids: list, time_step: int) -> list:
    '''
    Filter elements from scene_list that include target images.
    '''

    if len(target_ids) == 0:
      return []
    elif len(target_ids) == 1:
      return [scene_list[target_ids[0]]]

    filter_list = [None] * len(scene_list)

    for i in range(len(target_ids) - 1):
      start, end = target_ids[i], target_ids[i + 1]
      filter_list[start], filter_list[end] = scene_list[start], scene_list[end]

      if scene_list[end][0].get_seconds() - scene_list[start][1].get_seconds() <= time_step:
        filter_list[start:end] = scene_list[start:end]

    filter_list = [i for i in filter_list if i != None]

    return filter_list
  
  def save_scenes(self, video_path: str, output_path: str, scene_list: list):
    '''
    Save scene list, images and videos.
    '''
    if scene_list == []:
      return

    self.clear_folder(output_path)

    #save scene imgs
    scene_dir = os.path.join(output_path, SCENE_PATH)
    self.clear_folder(scene_dir)
    scenedetect.scene_manager.save_images(scene_list, self.video_manager, num_images=1, output_dir=scene_dir)

    #save scene list as csv file
    with open(os.path.join(output_path, CSV_FILE), 'w') as f:
      scenedetect.scene_manager.write_scene_list(f, scene_list)

    #save videos
    output_videoname = '$VIDEO_NAME-Scene$SCENE_NUMBER.mp4'
    videoname = output_path + '/' + ntpath.basename(output_path)
    video_splitter.split_video_ffmpeg([video_path], scene_list, output_videoname, videoname)

  def split_video(self, videoname: str):
    '''
    Clip shots of roles and B-rolls from the video.
    '''
    #init video_manager
    video_path = os.path.join(VIDEO_PATH, videoname)
    self.init_video_manager(video_path)
    self.video_manager.start()

    #detect scenes
    self.clear_folder(SCENE_PATH)
    scene_list, thumbnails = self.detect_scenes(SCENE_PATH)

    #replace illegal characters
    ep_name = os.path.splitext(videoname)[0]
    rstr = r"[\/\\\:\*\?\"\<\>\|]"  # '/ \ : * ? " < > |'
    ep_name = re.sub(rstr, "_", ep_name)
    
    output_dirs = []
    scene_lists = []
    #clip scenes
    if 0 in self.modes:
      output_dirs.append(os.path.join(CLIP_PATH, ep_name))
      scene_lists.append(scene_list)

    #clip role
    if 1 in self.modes:
      role_names = os.listdir(INPUT_PATH)
      output_dirs += [os.path.join(ROLE_PATH, role, ep_name) for role in role_names]

      for role in role_names: 
        role_imgs = self.recognize_role(os.path.join(INPUT_PATH, role))
        target_ids = [i for i, img_path in thumbnails.items() if img_path[0] in role_imgs]
        role_scene_list = self.filter_scene_list(scene_list, target_ids, ROLE_TIME_STEP)
        scene_lists.append(role_scene_list)

    #clip b-roll
    if 2 in self.modes:
      output_dirs.append(os.path.join(BROLL_PATH, ep_name))

      broll_imgs = self.detect_broll()
      target_ids = [i for i, img_path in thumbnails.items() if img_path[0] in broll_imgs]
      broll_scene_list = self.filter_scene_list(scene_list, target_ids, BROLL_TIME_STEP)
      scene_lists.append(broll_scene_list)

    #save output files
    for output_dir, scene_list in zip(output_dirs, scene_lists):
      self.save_scenes(video_path, output_dir, scene_list)

    self.video_manager.release()
    shutil.rmtree(SCENE_PATH, ignore_errors=True)
    
  def clip_episodes(self):
    '''
    Clip all videos.
    '''
    self.make_dirs()

    #replace Chinese characters
    videonames = []
    suffixs = ['.mp4', '.MP4', '.mkv', '.MKV', '.flv', '.FLV']
    for name in os.listdir(VIDEO_PATH):
      suffix = os.path.splitext(name)[-1]
      if suffix in suffixs:
        videonames.append(self.rename_filename(VIDEO_PATH, name))

    #start clip each episode
    for filename in videonames:
      t1 = time.time()
      self.split_video(filename)

      #count running time
      t2 = time.time()
      m, s = divmod(t2 - t1, 60)
      h, m = divmod(m, 60)
      print('%s uses %02d:%02d:%02d s.' % (filename, h, m, s))
            
if __name__ == '__main__':
  '''
  start_time: 'hh:mm:ss'
  end_time: 'hh:mm:ss'

  mode=0: clip scenes
  mode=1: clip role's shots
  mode=2: clip B-roll
  '''
  
  clip = EpClipper(start_time='00:00:00', end_time='00:02:00', modes=[0, 1, 2])
  #clip = EpClipper()
  clip.clip_episodes()