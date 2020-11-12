# -*- coding: utf8 -*-
from past.builtins import basestring
import os.path
from pathlib2 import Path
import rasterio
import numpy as np
from data.base_dataset import BaseDataset, get_transform
from data.image_folder import make_dataset
from PIL import Image
import random


class UnalignedMosaicDataset(BaseDataset):
    """
    This dataset class can load unaligned/unpaired datasets.

    It requires two directories to host training images from domain A '/path/to/data/trainA'
    and from domain B '/path/to/data/trainB' respectively.
    You can train the model with the dataset flag '--dataroot /path/to/data'.
    Similarly, you need to prepare two directories:
    '/path/to/data/testA' and '/path/to/data/testB' during test time.
    """

    def __init__(self, opt):
        """Initialize this dataset class.
        Parameters:
            opt (Option class) -- stores all the experiment flags; needs to be a subclass of BaseOptions
        """
        BaseDataset.__init__(self, opt)
        self.dir_A = os.path.join(opt.dataroot, 'ps_mosaic_chips/chips')  # create a path '/path/to/data/trainA'  dataroot是指定的数据文件夹,目前是./datasets/maps. 
        self.dir_B = os.path.join(opt.dataroot, 'skysat_mosaic_chips/chips')  # create a path '/path/to/data/trainB'

        self.A_paths = sorted(make_dataset(self.dir_A, opt.max_dataset_size))   # load images from '/path/to/data/trainA'
        self.B_paths = sorted(make_dataset(self.dir_B, opt.max_dataset_size))    # load images from '/path/to/data/trainB'
        self.A_size = len(self.A_paths)  # get the size of dataset A
        self.B_size = len(self.B_paths)  # get the size of dataset B
        btoA = self.opt.direction == 'BtoA'
        input_nc = self.opt.output_nc if btoA else self.opt.input_nc       # get the number of channels of input image
        output_nc = self.opt.input_nc if btoA else self.opt.output_nc      # get the number of channels of output image
        self.transform_A = get_transform(self.opt, grayscale=(input_nc == 1))
        self.transform_B = get_transform(self.opt, grayscale=(output_nc == 1))

    def __getitem__(self, index):
        """Return a data point and its metadata information.

        Parameters:
            index (int)      -- a random integer for data indexing

        Returns a dictionary that contains A, B, A_paths and B_paths
            A (tensor)       -- an image in the input domain
            B (tensor)       -- its corresponding image in the target domain
            A_paths (str)    -- image paths
            B_paths (str)    -- image paths
        """
        A_path = self.A_paths[index % self.A_size]  # make sure index is within then range A_size是文件夹里文件的数量
        if self.opt.serial_batches:   # make sure index is within then range
            index_B = index % self.B_size
        else:   # randomize the index for domain B to avoid fixed pairs. 决定是乱序还是配对
            index_B = random.randint(0, self.B_size - 1)
        B_path = self.B_paths[index_B]
        A_img, _ = load_geotiff_as_array_with_metadata(A_path)
        B_img, _ = load_geotiff_as_array_with_metadata(B_path)
        
        A_img = Image.fromarray(A_img[...,:3])  #Returns: An Image object. 这里才是真正读取图像文件
        B_img = Image.fromarray(B_img[...,:3])
        # apply image transformation
        A = self.transform_A(A_img) #transform_A是一个将PIL图像转换为tensor的函数，里面有各种选项
        B = self.transform_B(B_img)
        # print("get an item")
        # print(type(A)) #pytorch tensor 
        # print(type(B))
        # print(A_path)
        # print(B_path)  #[3,256,256]
        #os._exit(0)
        return {'A': A, 'B': B, 'A_paths': A_path, 'B_paths': B_path}  #A_path好像跟后续操作没有什么关系

    def __len__(self):
        """Return the total number of images in the dataset.

        As we have two datasets with potentially different number of images,
        we take a maximum of
        """
        #print(self.A_paths) #所有路径的集合
        #print(self.A_paths)
        return max(self.A_size, self.B_size)



def load_geotiff_as_array_with_metadata(path, bands=None, peek=False):
    """
    Util to load Geotiff into array, with georeferencing info

    Args:
        - path: the url of a file. Can be local or remote using vsi
        - bands (optional): An array of integers, the bands to read
        - peek (optional): If True, only return the metadata and tags

    Returns:
        - numpy array of per-band pixel values [Height, Width, Channels]
        - dict of metadata containing rasterio profile and crs, and tags which contains RPC for basic product: src.tags(ns='RPC')
    """
    if isinstance(path, basestring):
        path = Path(path)

    with rasterio.open(str(path)) as infile:
        metadata = {
            'meta': infile.meta,
            'tags': infile.tags,
            'tags_dict': {
                "RPC": infile.tags(ns='RPC')
            },
            'descriptions': infile.descriptions
        }

        if peek:
            return metadata

        if bands is not None:
            arr = infile.read(bands)
            metadata['meta'].update(count=len(bands))
        else:
            arr = infile.read()
        arr = np.rollaxis(arr, 0, 3)

        return arr, metadata