#coding=utf-8
import torch
import torch.utils.data as data
import torchvision.transforms as transforms

from PIL import Image
from PIL import ImageDraw

import os.path as osp
import numpy as np
import json

class CPDataset(data.Dataset):
    """Dataset for CP-VTON.
    """
    def __init__(self, opt):
        super(CPDataset, self).__init__()
        # base setting
        self.opt = opt
        self.root = opt.dataroot
        self.datamode = opt.datamode # train or test or self-defined
        self.stage = opt.stage # GMM or TOM
        self.data_list = opt.data_list
        self.fine_height = opt.fine_height
        self.fine_width = opt.fine_width
        self.radius = opt.radius
        self.data_path = osp.join(opt.dataroot, opt.datamode)
        self.to_tensor_and_norm = transforms.Compose([
                transforms.ToTensor(),
                transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])
        
        # load data list
        im_names = []
        c_names = []
        with open(osp.join(opt.dataroot, opt.data_list), 'r') as f:
            for line in f.readlines():
                im_name, c_name = line.strip().split()
                im_names.append(im_name)
                c_names.append(c_name)

        self.im_names = im_names
        self.c_names = c_names

    def name(self):
        return "CPDataset"

    # how should we restructure this?
    # basically we're just increasing the pose representation
    # and the cloth representation
    # so if we put these all into little functions
    # should work well


    ########################
    # CLOTH REPRESENTATION
    ########################

    def get_cloth_representation(self, index):
        """
        call all cloth loaders
        :param index:
        :return:
        """
        pass

    def get_input_cloth(self, index):
        """ from cp-vton """
        c_name = self.c_names[index]
        folder = "cloth" if self.stage == "GMM" else "warp-cloth"
        c = Image.open(osp.join(self.data_path, folder, c_name))
        c = self.to_tensor_and_norm(c)  # [-1,1]
        return c

    def get_input_cloth_mask(self, index):
        """from cp-vton"""
        c_name = self.c_names[index]
        folder = "cloth-mask" if self.stage == "GMM" else "warp-mask"
        cm = Image.open(osp.join(self.data_path, folder, c_name))
        cm_array = np.array(cm)
        cm_array = (cm_array >= 128).astype(np.float32)
        cm = torch.from_numpy(cm_array)  # [0,1]
        cm.unsqueeze_(0)
        return cm

    def get_input_cloth_mesh(self, index):
        """ TODO: us, from mgn"""
        pass

    def get_target_worn_cloth(self, im, _parse_array):
        """from cp-vton, cloth texture as it is worn on the person"""
        # ISOLATE CLOTH. cloth labels, combines into a 1d binary mask
        _parse_cloth = (_parse_array == 5).astype(np.float32) + \
                       (_parse_array == 6).astype(np.float32) + \
                       (_parse_array == 7).astype(np.float32)
        _parse_cloth_mask = torch.from_numpy(_parse_cloth) # [0,1]
        # upper cloth, segment it from the body
        im_c = im * _parse_cloth_mask + (1 - _parse_cloth_mask) # [-1,1], fill 1 for other parts
        return im_c

    ########################
    # PERSON REPRESENTATION
    ########################

    def get_person_representation(self, index):
        """
        get all person represetations
        :param index:
        :return:
        """
        pass

    def _get_person_rgb(self, index):
        """
        helper function to get the person image; not used as input to the network. used
        instead to form the other input
        :param index:
        :return:
        """
        # person image
        im_name = self.im_names[index]
        im = Image.open(osp.join(self.data_path, 'image', im_name))
        im = self.to_tensor_and_norm(im) # [-1,1]
        return im

    def _get_person_parsed(self, index):
        # load parsing image
        im_name = self.im_names[index]
        parse_name = im_name.replace('.jpg', '.png')
        im_parse = Image.open(osp.join(self.data_path, 'image-parse', parse_name))
        parse_array = np.array(im_parse)
        return parse_array

    def get_input_person_pose(self, index):
        """from cp-vton, loads the pose as white squares
        returns pose map, image of pose map
        """
        # load pose points
        im_name = self.im_names[index]
        _pose_name = im_name.replace('.jpg', '_keypoints.json')
        with open(osp.join(self.data_path, 'pose', _pose_name), 'r') as f:
            pose_label = json.load(f)
            pose_data = pose_label['people'][0]['pose_keypoints']
            pose_data = np.array(pose_data)
            pose_data = pose_data.reshape((-1,3))

        point_num = pose_data.shape[0] # how many pose joints
        pose_map = torch.zeros(point_num, self.fine_height, self.fine_width) # constructs an N-channel map

        r = self.radius
        im_pose = Image.new('L', (self.fine_width, self.fine_height))
        pose_draw = ImageDraw.Draw(im_pose)

        # draws a big white square around the joint on the appropriate channel. I guess this emphasizes it
        for i in range(point_num):
            one_map = Image.new('L', (self.fine_width, self.fine_height))
            one_map_tensor = self.to_tensor_and_norm(one_map)
            pose_map[i] = one_map_tensor[0]

            draw = ImageDraw.Draw(one_map)
            pointx = pose_data[i,0]
            pointy = pose_data[i,1]
            if pointx > 1 and pointy > 1:
                draw.rectangle((pointx-r, pointy-r, pointx+r, pointy+r), 'white', 'white')
                pose_draw.rectangle((pointx-r, pointy-r, pointx+r, pointy+r), 'white', 'white')

        # just for visualization
        im_pose = self.to_tensor_and_norm(im_pose)

        return pose_map, im_pose

    def get_input_person_head(self, im, _parse_array):
        """ from cp-vton, get the floating head alone"""
        # ISOLATE HEAD. head parts, probably face, hair, sunglasses. combines into a 1d binary mask
        _parse_head = (_parse_array == 1).astype(np.float32) + \
                      (_parse_array == 2).astype(np.float32) + \
                      (_parse_array == 4).astype(np.float32) + \
                      (_parse_array == 13).astype(np.float32)
        _phead = torch.from_numpy(_parse_head) # [0,1]
        im_h = im * _phead - (1 - _phead) # [-1,1], fill 0 for other parts
        return im_h

    def get_input_person_body_shape(self, _parse_array):
        """ from cp-vton, the body silhouette """
        # ISOLATE BODY SHAPE
        # removes the background
        _parse_shape = (_parse_array > 0).astype(np.float32)
        # shape downsample, reduces resolution, makes the shape "blurry"
        _parse_shape = Image.fromarray((_parse_shape*255).astype(np.uint8))
        _parse_shape = _parse_shape.resize((self.fine_width//16, self.fine_height//16), Image.BILINEAR)
        _parse_shape = _parse_shape.resize((self.fine_width, self.fine_height), Image.BILINEAR)
        shape = self.to_tensor_and_norm(_parse_shape) # [-1,1]
        return shape

    def __getitem__(self, index):
        # input cloth
        cloth = self.get_input_cloth(index)
        cloth_mask = self.get_input_cloth_mask(index)

        # person image
        im = self._get_person_rgb(index)
        # TODO: combine the below into a get_person_representation() function.
        #  I want all functions in __getitem__ to be independent and only indexed based
        # load parsing image
        _parse_array = self._get_person_parsed(index)
        # body shape
        shape = self.get_input_person_body_shape(_parse_array)
        # isolated head
        im_h = self.get_input_person_head(im, _parse_array)
        # isolated cloth
        im_c = self.get_target_worn_cloth(im, _parse_array)

        # load pose points
        pose_map, im_pose = self.get_input_person_pose(index)

        # cloth-agnostic representation
        agnostic = torch.cat([shape, im_h, pose_map], 0) 

        if self.stage == 'GMM':
            im_g = Image.open('../grid.png')
            im_g = self.to_tensor_and_norm(im_g)
        else:
            im_g = ''

        result = {
            'c_name':   self.c_names[index],     # for visualization
            'im_name':  self.im_names[index],    # for visualization or ground truth
            'cloth':    cloth,          # for input
            'cloth_mask':     cloth_mask,   # for input
            'image':    im,         # for visualization
            'agnostic': agnostic,   # for input
            'parse_cloth': im_c,    # for ground truth
            'shape': shape,         # for visualization
            'head': im_h,           # for visualization
            'pose_image': im_pose,  # for visualization
            'grid_image': im_g,     # for visualization
            }

        return result

    def __len__(self):
        return len(self.im_names)

class CPDataLoader(object):
    def __init__(self, opt, dataset):
        super(CPDataLoader, self).__init__()

        if opt.shuffle :
            train_sampler = torch.utils.data.sampler.RandomSampler(dataset)
        else:
            train_sampler = None

        self.data_loader = torch.utils.data.DataLoader(
                dataset, batch_size=opt.batch_size, shuffle=(train_sampler is None),
                num_workers=opt.workers, pin_memory=True, sampler=train_sampler)
        self.dataset = dataset
        self.data_iter = self.data_loader.__iter__()
       
    def next_batch(self):
        try:
            batch = self.data_iter.__next__()
        except StopIteration:
            self.data_iter = self.data_loader.__iter__()
            batch = self.data_iter.__next__()

        return batch


if __name__ == "__main__":
    print("Check the dataset for geometric matching module!")
    
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataroot", default = "data")
    parser.add_argument("--datamode", default = "train")
    parser.add_argument("--stage", default = "GMM")
    parser.add_argument("--data_list", default = "train_pairs.txt")
    parser.add_argument("--fine_width", type=int, default = 192)
    parser.add_argument("--fine_height", type=int, default = 256)
    parser.add_argument("--radius", type=int, default = 3)
    parser.add_argument("--shuffle", action='store_true', help='shuffle input data')
    parser.add_argument('-b', '--batch-size', type=int, default=4)
    parser.add_argument('-j', '--workers', type=int, default=1)
    
    opt = parser.parse_args()
    dataset = CPDataset(opt)
    data_loader = CPDataLoader(opt, dataset)

    print('Size of the dataset: %05d, dataloader: %04d' \
            % (len(dataset), len(data_loader.data_loader)))
    first_item = dataset.__getitem__(0)
    first_batch = data_loader.next_batch()

    from IPython import embed; embed()

