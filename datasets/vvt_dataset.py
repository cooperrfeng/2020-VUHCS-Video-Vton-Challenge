# coding=utf-8
import torch
from glob import glob
import torch
import torch.utils.data as data
import torchvision.transforms as transforms

from PIL import Image
from PIL import ImageDraw
from overrides import overrides

from datasets.cpvton_dataset import CpVtonDataset, CPDataLoader

import os
import os.path as osp
import numpy as np
import json


class VVTDataset(CpVtonDataset):
    """ CP-VTON dataset with the VVT folder structure. """

    def __init__(self, opt):
        super(VVTDataset, self).__init__(opt)
        del self.data_list  # not using this
        del self.data_path

    #@overrides(CpVtonDataset)
    def load_file_paths(self):
        """ Reads the datalist txt file for CP-VTON"""
        self.root = self.opt.vvt_dataroot  # override this
        folder = f"lip_{self.opt.datamode}_frames"
        self.image_names = sorted(glob(f"{self.root}/{folder}/**/*.png"))

    @staticmethod
    def extract_folder_id(image_path):
        return image_path.split(os.sep)[-2]

    ########################
    # CLOTH REPRESENTATION
    ########################

    #@overrides(CpVtonDataset)
    def get_input_cloth_path(self, index):
        image_path = self.image_names[index]
        folder_id = VVTDataset.extract_folder_id(image_path)

        subdir = "lip_clothes_person" if self.stage == "GMM" else "warp-cloth"
        cloth_folder = osp.join(self.root, subdir, folder_id)
        cloth_path = glob(f"{cloth_folder}/*cloth*")[0]
        return cloth_path

    #@overrides(CpVtonDataset)
    def get_input_cloth_name(self, index):
        cloth_path = self.get_input_cloth_path(index)
        folder_id = VVTDataset.extract_folder_id(cloth_path)
        base_cloth_name = osp.basename(cloth_path)
        frame_name = osp.basename(self.get_person_image_name(index))
        # e.g. 4he21d00f-g11/4he21d00f-g11@10=cloth_front.jpg
        name = osp.join(folder_id, f"{base_cloth_name}.FOR.{frame_name}")
        return name

    ########################
    # PERSON REPRESENTATION
    ########################
    #@overrides(CpVtonDataset)
    def get_person_image_path(self, index):
        # because we globbed, the path is the list
        return self.image_names[index]

    #@overrides(CpVtonDataset)
    def get_person_image_name(self, index):
        image_path = self.get_person_image_path(index)
        folder_id = VVTDataset.extract_folder_id(image_path)
        name = osp.join(folder_id, osp.basename(image_path))
        return name

    #@overrides(CpVtonDataset)
    def get_person_parsed_path(self, index):
        image_path = self.get_person_image_path(index)
        folder = f"lip_{self.opt.datamode}_frames_parsing"
        id = VVTDataset.extract_folder_id(image_path)
        parsed_fname = os.path.split(image_path)[-1].replace(".png", "_label.png")
        parsed_path = osp.join(self.root, folder, id, parsed_fname)
        if not os.path.exists(parsed_path):  # hacky, if it doesn't exist as _label, then try getting rid of it. did this to fix my specific bug in a time crunch
            parsed_path = parsed_path.replace("_label", "")
        return parsed_path

    #@overrides(CpVtonDataset)
    def get_input_person_pose_path(self, index):
        image_path = self.get_person_image_path(index)
        folder = f"lip_{self.opt.datamode}_frames_keypoint"
        id = VVTDataset.extract_folder_id(image_path)

        keypoint_fname = os.path.split(image_path)[-1].replace(
            ".png", "_keypoints.json"
        )

        pose_path = osp.join(self.root, folder, id, keypoint_fname)
        return pose_path


if __name__ == "__main__":
    print("Check the dataset for geometric matching module!")

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dataroot", default="data")
    parser.add_argument("--vvt_dataroot", default="/data_hdd/vvt_competition")
    parser.add_argument("--datamode", default="train")
    parser.add_argument("--stage", default="GMM")
    parser.add_argument("--data_list", default="train_pairs.txt")
    parser.add_argument("--fine_width", type=int, default=192)
    parser.add_argument("--fine_height", type=int, default=256)
    parser.add_argument("--radius", type=int, default=3)
    parser.add_argument("--shuffle", action="store_true", help="shuffle input data")
    parser.add_argument("-b", "--batch-size", type=int, default=4)
    parser.add_argument("-j", "--workers", type=int, default=1)

    opt = parser.parse_args()
    dataset = VVTDataset(opt)
    data_loader = CPDataLoader(opt, dataset)

    print(
        "Size of the dataset: %05d, dataloader: %04d"
        % (len(dataset), len(data_loader.data_loader))
    )
    first_item = dataset.__getitem__(0)
    first_batch = data_loader.next_batch()

    from IPython import embed

    embed()
