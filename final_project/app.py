import os
import time
from threading import Thread
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests
from googletrans import Translator

# BrowserStack credentials
BROWSERSTACK_USERNAME = " "##give the username
BROWSERSTACK_ACCESS_KEY = " "##give the access key
BROWSERSTACK_URL = f"https://{BROWSERSTACK_USERNAME}:{BROWSERSTACK_ACCESS_KEY}@hub-cloud.browserstack.com/wd/hub"

# Create an 'images' directory if it doesn't exist
image_dir = "./images"
os.makedirs(image_dir, exist_ok=True)

# Browser configurations for parallel testing
BROWSER_CONFIGS = [
    {"browserName": "Chrome", "browserVersion": "latest", "os": "Windows", "osVersion": "10"},
    {"browserName": "Firefox", "browserVersion": "latest", "os": "Windows", "osVersion": "10"},
    {"browserName": "Safari", "browserVersion": "latest", "os": "OS X", "osVersion": "Big Sur"},
    {"browserName": "Chrome", "osVersion": "11.0", "deviceName": "Samsung Galaxy S22", "realMobile": True},
    {"browserName": "Safari", "osVersion": "16", "deviceName": "iPhone 14", "realMobile": True},
]


def scrape_el_pais(browser_config):
    """
    Function to scrape El País Opinion section using a given BrowserStack configuration.
    """
    print(f"Starting test on: {browser_config}")

    # Update capabilities for BrowserStack
    capabilities = {
        "bstack:options": {
            "os": browser_config.get("os", ""),
            "osVersion": browser_config.get("osVersion", ""),
            "deviceName": browser_config.get("deviceName", ""),
            "realMobile": browser_config.get("realMobile", False),
            "local": "false",
            "seleniumVersion": "4.8.0",
        },
        "browserName": browser_config["browserName"],
        "browserVersion": browser_config.get("browserVersion", ""),
    }

    # Create the appropriate options based on the browser name
    if browser_config["browserName"] == "Chrome":
        options = webdriver.ChromeOptions()
    elif browser_config["browserName"] == "Firefox":
        options = webdriver.FirefoxOptions()
    elif browser_config["browserName"] == "Safari":
        options = webdriver.SafariOptions()
    else:
        raise ValueError(f"Unsupported browser: {browser_config['browserName']}")

    # Set the options to capabilities for BrowserStack
    options.add_argument("--start-maximized")
    capabilities.update(options.to_capabilities())

    # Initialize WebDriver with BrowserStack capabilities
    driver = webdriver.Remote(
        command_executor=BROWSERSTACK_URL,
        options=options
    )

    try:
        # Navigate to El País Opinion section
        driver.get('https://elpais.com/')
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "Opinión"))
        )

        # Close any pop-ups or overlays
        try:
            accept_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Accept')]"))
            )
            accept_button.click()
            print("Accepted cookie consent.")
        except Exception as e:
            print(f"No cookie consent banner found or already handled: {e}")

        # Click on the Opinion section
        driver.find_element(By.LINK_TEXT, "Opinión").click()

        # Wait for the page to load
        time.sleep(3)

        # Fetch the page content using BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Find the first five articles in the Opinion section
        articles = soup.find_all('article', limit=5)

        article_data = []

        # Loop through the articles and fetch title and link
        for article in articles:
            title = article.find('h2').get_text(strip=True)  # Article title
            article_link = article.find('a')['href'] if article.find('a') else None
            article_info = {'title': title, 'link': article_link}
            article_data.append(article_info)

        # Navigate to each article's page and fetch its content
        for article in article_data:
            if article['link']:
                # Open the article page
                driver.get(article['link'])

                # Wait for the content to load
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "article"))
                    )
                except Exception as e:
                    print(f"Timeout or error loading article: {article['title']}")
                    article['content'] = "Content not found"
                    continue

                # Fetch the page content
                article_soup = BeautifulSoup(driver.page_source, 'html.parser')

                # Try various content containers
                content_div = article_soup.find('div', {'class': 'article_body'})
                if not content_div:
                    content_div = article_soup.find('article')  # Use <article> tag as a fallback
                if not content_div:
                    content_div = article_soup.find('div', {'class': 'content'})

                # Extract the text
                content = content_div.get_text(strip=True) if content_div else "Content not found"
                article['content'] = content

                # Fetch and save the image
                image_tag = article_soup.find('img')
                if image_tag and image_tag.get('src'):
                    image_url = image_tag['src']
                    if image_url.startswith('https'):  # Check if the URL is absolute
                        img_data = requests.get(image_url).content
                        img_name = f"{article['title'][:30].replace(' ', '_')}.jpg"  # Replace spaces with underscores
                        img_path = os.path.join(image_dir, img_name)
                        with open(img_path, 'wb') as img_file:
                            img_file.write(img_data)
                        article['image'] = img_path

        # Translate the titles to English using Google Translate API
        translator = Translator()

        translated_titles = []
        for article in article_data:
            translated_title = translator.translate(article['title'], src='es', dest='en').text
            translated_titles.append(translated_title)

        # Analyze repeated words in the translated titles
        word_count = {}
        for title in translated_titles:
            words = title.split()
            for word in words:
                word = word.lower()
                word_count[word] = word_count.get(word, 0) + 1

        # Filter out words repeated more than twice
        repeated_words = {word: count for word, count in word_count.items() if count > 2}

        # Print the original articles and their translated titles
        for article, translated_title in zip(article_data, translated_titles):
            print(f"Original Title: {article['title']}")
            print(f"Content: {article['content']}")
            print(f"Translated Title: {translated_title}")
            if 'image' in article:
                print(f"Image saved at: {article['image']}")
            print("------")

        # Print repeated words and their count
        print("\nRepeated Words in Translated Titles:")
        for word, count in repeated_words.items():
            print(f"{word}: {count}")

    finally:
        # Close the WebDriver
        driver.quit()


# Run tests in parallel threads
threads = []
for config in BROWSER_CONFIGS:
    thread = Thread(target=scrape_el_pais, args=(config,))
    threads.append(thread)
    thread.start()

# Wait for all threads to complete
for thread in threads:
    thread.join()
