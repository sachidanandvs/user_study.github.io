import os
# import shutil
import glob
# import pillow
import img2pdf
from PIL import Image, ImageDraw

results_folder = "./generated_human_study"

baselines = os.listdir(results_folder)

num_of_slides_wide = 2
num_of_slides_height = 2
num_of_slides_per_page = num_of_slides_wide * num_of_slides_height

for baseline in baselines:
    for paper_names in os.listdir(os.path.join(results_folder, baseline)):
        if(not os.path.isdir(os.path.join(results_folder, baseline, paper_names))):
            continue
        paper_name = paper_names.split("_")[0]
        print(f"Processing {paper_name}...")
        images_list = glob.glob(os.path.join(results_folder, baseline, paper_names, "final_rendered", "slide_*.png"))
        images_list.sort()
        # print("images_list: ", images_list)
        # if(os.path.exists(output_pdf_path)):
        #     print(f"Output PDF {output_pdf_path} already exists, skipping rendering for {paper_name}")
        # continue

        combined_images = []
        first_image = Image.open(images_list[0])
        width, height = first_image.size
        combined_folder = os.path.join(results_folder, baseline, paper_names, "combined_images")
        os.makedirs(combined_folder, exist_ok=True)
        for i in range(0, len(images_list), num_of_slides_per_page):
            images_to_combine = images_list[i:i+num_of_slides_per_page]
            combined_image = Image.new('RGB', (width * num_of_slides_wide, height * num_of_slides_height), color='white')
            for j, image_path in enumerate(images_to_combine):
                image = Image.open(image_path)
                combined_image.paste(image, (width * (j % num_of_slides_wide), height * (j // num_of_slides_wide)))
            # Draw black separator lines between slides
            draw = ImageDraw.Draw(combined_image)
            sep = 3  # line thickness in pixels
            # Vertical separator(s)
            for col in range(1, num_of_slides_wide):
                x = width * col
                draw.rectangle([x - sep // 2, 0, x + sep // 2, height * num_of_slides_height], fill="black")
            # Horizontal separator(s)
            for row in range(1, num_of_slides_height):
                y = height * row
                draw.rectangle([0, y - sep // 2, width * num_of_slides_wide, y + sep // 2], fill="black")
            combined_image_path = os.path.join(combined_folder, f"combined_{i:02d}.png")
            combined_image.save(combined_image_path)
            combined_images.append(combined_image_path)
        
        output_pdf_path = os.path.join(results_folder, baseline, paper_names, f"{paper_name}_{baseline}_combined.pdf")
        with open(output_pdf_path, "wb") as f:
            f.write(img2pdf.convert(combined_images))
        print(f"Saved combined PDF for {paper_name} at {output_pdf_path}")


    print(f"Finished processing baseline {baseline}")

print("Finished processing all baselines")