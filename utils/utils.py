import os
import urllib.request
from urllib.parse import quote
import zipfile
import numpy as np
import pandas as pd


def softmax(x):
    y = np.exp(x - np.max(x))
    f_x = y / np.sum(np.exp(x))
    return f_x


def softmax2d(x):
    max = np.max(x, axis=1, keepdims=True) 
    e_x = np.exp(x - max)
    sum = np.sum(e_x, axis=1, keepdims=True)
    f_x = e_x / sum 
    return f_x

# =============================================================================
# download function
# =============================================================================
def show_progress(block_num, block_size, total_size):
    bar_template = "\r[{}] {:.2f}%"

    downloaded = block_num * block_size
    p = downloaded / total_size * 100
    i = int(downloaded / total_size * 30)
    if p >= 100.0: p = 100.0
    if i >= 30: i = 30
    bar = "#" * i + "." * (30 - i)
    print(bar_template.format(bar, p), end='')


def get_file(url, file_name=None, cache_dir='./data/'):
    """Download a file from the `url` if it is not in the cache.
    The file at the `url` is downloaded to the `./data`.
    Args:
        url (str): URL of the file.
        file_name (str): Name of the file. It `None` is specified the original
            file name is used.
    Returns:
        str: Absolute path to the saved file.
    """
    url_splited = url.split('/')
    url = '/'.join(url_splited[:2]) + '/' + quote('/'.join(url_splited[2:])) # (% incoding)

    if file_name is None:
        file_name = url[url.rfind('/') + 1:]
    file_path = os.path.join(cache_dir, file_name)

    os.makedirs(cache_dir, exist_ok=True)

    if os.path.exists(file_path):
        return file_path

    print("Downloading: " + file_name)
    try:
        urllib.request.urlretrieve(url, file_path, show_progress)
    except (Exception, KeyboardInterrupt) as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    print(" Done")

    return file_path


def unzip(file_path, unzip_path='./data/'):
    os.makedirs(unzip_path, exist_ok=True)
    zipdata = zipfile.ZipFile(file_path)
    zipinfos = zipdata.infolist()

    for zipinfo in zipinfos:
        file_name = zipinfo.filename
        file_name_old = file_name.encode('cp437').decode('euc-kr')
        
        if 'train' in file_name:
            file_name = 'train.zip'
        elif 'test' in file_name:
            file_name = 'test.zip'
        
        if not os.path.isfile(unzip_path + file_name):
            zipinfo.filename = file_name
            zipdata.extract(zipinfo, unzip_path)

        if '.zip' in file_name:
            unzip_dir = file_name.replace('.zip', '') + '/'
            unzip_path2 = unzip_path + unzip_dir
            
            if not os.path.isdir(unzip_path2):
                os.makedirs(unzip_path2, exist_ok=True)
                unzip(unzip_path+file_name, unzip_path2)
                print('압축 해제 완료! - ' + file_name_old + ' -> ' + unzip_dir)
    
    zipdata.close()


# =============================================================================
# read function
# ============================================================================= 

def read_csv(csv_path, return_dict=False):
    df = pd.read_csv(csv_path)
    if return_dict:
        return df.to_dict('list')

    col_list = []
    for col in df.keys():
        col_list.append(df[col].tolist())
    
    return (*col_list,)
