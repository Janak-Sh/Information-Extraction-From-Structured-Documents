import os
import sys

special = {
    "transformers": "git+https://github.com/huggingface/transformers.git",
    "detectron2": "git+https://github.com/facebookresearch/detectron2.git"
}

exclude = list(special.keys())+["torch", "torchvision", "torchaudio", "nvidia-cublas-cu11",
                                "nvidia-cuda-nvrtc-cu11", "nvidia-cuda-runtime-cu11", "nvidia-cudnn-cu11"]

try:
    option = sys.argv[1]
except:
    raise ValueError("Expected i or g as argument")

if (option == "i"):
    os.system("pip install -r requirements.txt")
    os.system("pip install torch==1.12.1+cpu torchvision==0.13.1+cpu  --extra-index-url https://download.pytorch.org/whl/cpu")
    for i in special:
        os.system(f"pip install {special[i]}")
elif (option == "g"):
    os.system("pip freeze > requirements.txt")
    with open("requirements.txt", "r") as req:
        lines = req.readlines()
        temp = []
        for i in lines:
            if (i.split(' ')[0] not in exclude and i.split('==')[0] not in exclude):
                temp.append(i)

    open("requirements.txt", "w").write(''.join(temp))

else:
    raise ValueError("Invalid option. Provide i or g.")
