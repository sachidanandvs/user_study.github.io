import os
import glob
# import utils.src.utils.ppt_to_images as ppt_to_images
import tempfile
import subprocess
from pathlib import Path
from PIL import Image
from pdf2image import convert_from_path
from utils.src.utils import tenacity
# from tenacity import retry, stop_after_attempt, wait_random
# from tenacity.log import tenacity_log

# tenacity = retry(
#     wait=wait_random(3), stop=stop_after_attempt(5), after=tenacity_log, reraise=True
# )

os.environ["PATH"] = f"{os.path.expanduser('~/libreoffice/opt/libreoffice25.8/program/')}:" + os.environ["PATH"]

pjoin = os.path.join
pexists = os.path.exists
pbasename = os.path.basename

@tenacity
def ppt_to_images(file: str, output_dir: str, warning: bool = False, dpi=72, output_type='png'):
    assert pexists(file), f"File {file} does not exist"
    if pexists(output_dir) and warning:
        print(f"ppt2images: {output_dir} already exists")
    os.makedirs(output_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create unique user installation directory for LibreOffice to avoid concurrency issues
        with tempfile.TemporaryDirectory() as user_install_dir:
            command_list = [
                "soffice",
                "--headless",
                "--norestore",
                "--nolockcheck",
                f"-env:UserInstallation=file://{user_install_dir}",
                "--convert-to",
                "pdf",
                file,
                "--outdir",
                temp_dir,
            ]
            # Set environment to ensure UTF-8 encoding
            env = os.environ.copy()
            env['LC_ALL'] = 'en_US.UTF-8'
            env['LANG'] = 'en_US.UTF-8'
            subprocess.run(command_list, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)

        for f in os.listdir(temp_dir):
            if not f.endswith(".pdf"):
                continue
            temp_pdf = pjoin(temp_dir, f)
            images = convert_from_path(temp_pdf, dpi=72)
            for i, img in enumerate(images):
                if output_type == 'png':
                    img.save(pjoin(output_dir, f"slide_{i+1:04d}.png"), 'PNG')
                else:
                    img.save(pjoin(output_dir, f"slide_{i+1:04d}.jpg"), 'JPEG')
            return

        raise RuntimeError("No PDF file was created in the temporary directory", file)


# @tenacity
# def ppt_to_images2(file: str, output_dir: str, warning: bool = False):
#     assert pexists(file), f"File {file} does not exist"
#     if pexists(output_dir) and warning:
#         print(f"ppt2images: {output_dir} already exists")
#     os.makedirs(output_dir, exist_ok=True)
#     with tempfile.TemporaryDirectory() as temp_dir:
#         command_list = [
#             "soffice",
#             "--headless",
#             "--convert-to",
#             "pdf",
#             file,
#             "--outdir",
#             temp_dir,
#         ]
#         subprocess.run(command_list, check=True, stdout=subprocess.DEVNULL)

#         for f in os.listdir(temp_dir):
#             if not f.endswith(".pdf"):
#                 continue
#             temp_pdf = pjoin(temp_dir, f)
#             images = convert_from_path(temp_pdf, dpi=72)
#             for i, img in enumerate(images):
#                 img.save(pjoin(output_dir, f"slide_{i+1:04d}.jpg"))
#             return

#         raise RuntimeError("No PDF file was created in the temporary directory", file)

def render_slides_from_folder(folder_path):
    files_path = glob.glob(os.path.join(folder_path, "**", "*.pptx"), recursive=True)
    print(f"Found {len(files_path)} files to render")
    for pptx_path in files_path:
        if(pptx_path.endswith(".pptx")):
            output_dir = os.path.dirname(pptx_path)
            print(f"Rendering slides from {pptx_path} to {output_dir}")
            output_dir = os.path.join(output_dir, os.path.basename(pptx_path).replace(".pptx", "_rendered"))
            if(os.path.exists(output_dir)):
                print(f"Output directory {output_dir} already exists, skipping rendering for {pptx_path}")
                continue
            os.makedirs(output_dir, exist_ok=True)
            ppt_to_images(pptx_path, output_dir)
            print(f"Rendered slides from {pptx_path} to {output_dir}")
        else:
            print(f"Skipping non-pptx file {pptx_path}")

if __name__ == "__main__":
    # render_slides_from_folder("../PPTAgent-experiment/generated_visuals")
    render_slides_from_folder("../PPTAgent-experiment/generated_visuals/ours_qwen3_vl_30_final_new")