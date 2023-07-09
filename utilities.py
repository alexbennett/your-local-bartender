import requests
import datetime
import os

import config

def download_images(image_urls, directory):
    """
    Downloads images from a list of URLs and saves them to a specified directory.

    Args:
        image_urls (List[str]): List of image URLs.
        directory (str): Directory path to save the downloaded images.

    Returns:
        List[str]: List of paths to the downloaded images.
    """
    os.makedirs(directory, exist_ok=True)
    imgs = []

    for i, url in enumerate(image_urls):
        response = requests.get(url)
        image_path = os.path.join(
            directory,
            f"image{i+1}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.jpg",
        )

        with open(image_path, "wb") as file:
            file.write(response.content)

        print(f"Image {i+1} downloaded: {image_path}")

        imgs.append(image_path)

    return imgs


def call_image_generation_api(prompt, n=1, size="512x512"):
    """
    Calls the OpenAI API to generate images based on a prompt.

    Args:
        prompt (str): Prompt for generating the images.
        n (int, optional): Number of images to generate. Defaults to 1.
        size (str, optional): Size of the generated images. Defaults to "512x512".

    Returns:
        List[str]: List of URLs for the generated images.
    """
    # Create the request body
    data = {"prompt": prompt, "n": n, "size": size}

    # Set up headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
    }

    # Send the request to generate images
    response = requests.post(
        "https://api.openai.com/v1/images/generations", headers=headers, json=data
    )
    response_json = response.json()

    print(response_json)

    # Extract the generated image URLs from the response
    image_urls = [result["url"] for result in response_json["data"]]

    return image_urls