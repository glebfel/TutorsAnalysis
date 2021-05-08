import re
import os
import json
import pymysql
import logging
import string
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from WriteToDatabase import WriteToDatabase

module = logging.getLogger('ParseWeb.RepetitRuParser')

class RepetitRuParser():
    
    MAIN_URL = "https://repetit.ru/repetitors/"
    logger = logging.getLogger("ParseWeb.RepetitRuParser")

    def __init__(self):
        """
        Class constructor
        """
        self.link_list = []
        self.cat_profiles_dict = {}

    def get_category_links(self):
        """
        Gets categories and their links for later parsing
        """
        logger.info("Gathering categories links...")
        try:
            self.driver.get(self.MAIN_URL)
            menu = self.driver.find_elements_by_class_name("dropdown-menu")
            categories = menu[0].find_elements_by_tag_name("a")
        except:
            logger.critical("Problems with Internet connection or Web driver occured! Cannot gather category list!")
            return
        # Gather link_list
        for cat in categories:
            link = cat.get_attribute("href")
            if("#" not in link):
               self.link_list.append(link)
        logger.info(f'Found {len(self.link_list)} categories!')

    def get_profiles_by_category(self, cat_link: str):
        """
        Gets list of repetitors (or other profi) by category link
        """
        self.driver.get(cat_link)
        profiles_links = []
        page_suffix = "?page="
        number = int(re.split(r"[ор]", self.driver.find_element_by_id('ctl00_ContentPlaceHolder1_SearchResultsNewControl_hResultsCount').text)[1])//10
        for page in range(2, number + 1):
            profiles = self.driver.find_elements_by_class_name("teachers")
            profiles = profiles[0].find_elements_by_class_name("teacher-name")
            for person in profiles:
                profiles_links.append(person.get_attribute("href"))
            self.driver.get(f"{cat_link}{page_suffix}{page}")
        return profiles_links

    def get_person_info(self, link: str) -> dict:
        """
        Parses person by link and returns dictionary with reviews, education info, tution experience, prices, etc.
        """
        self.driver.get(link)
        person_info = {}
        # Get person name
        person_info["ФИО"] = self.driver.find_element_by_class_name('teacher-name').text
        # Get education info
        edu = self.driver.find_element_by_class_name("education")
        person_info["Образование"] = edu.text.split("\n")[1]
        # Get age
        age = self.driver.find_elements_by_class_name('col-8')
        person_info["Возраст"] = int(re.split(r"[гл]", age[0].text)[0])
        # Get tution experience
        exp = self.driver.find_elements_by_class_name('col-8')
        person_info["Репетиторский опыт (лет)"] = int(re.split(r"[гл]", exp[0].text)[0])
        # Get number of reviews
        reviews = self.driver.find_element_by_xpath("//div[@class='reviews in-nav']//div[@class='section-header']")
        reviews = reviews.find_elements_by_tag_name('span')
        person_info["Количество оценок"] = reviews[0].text
        # Get reviews
        rate_list = ['Оценка 0', 'Оценка 1', 'Оценка 2', 'Оценка 3', 'Оценка 4', 'Оценка 5']
        for rate in rate_list:
            person_info[rate] = 0
        reviews = self.driver.find_elements_by_xpath("//div[@class='review-features']//div[@class='star-rating']")
        for rev in reviews:
            stars = rev.find_elements_by_tag_name("i")
            count = 0
            for s in stars:
                if(s.get_attribute("class") == "icon-star w10"):
                    count+=1
            person_info[rate_list[count]] += 1
        # Get all services and prices and methods of works
        services = self.driver.find_element_by_xpath("//div[@class='subjects in-nav']")
        if ("90 мин" in services.text):
            mins = "90 мин"
        elif ("45 мин" in services.text):
            mins = "45 мин"
        else:
            mins = "60 мин"
        services = services.find_elements_by_xpath("//div[@class='subject-header row']")
        names = self.driver.find_elements_by_xpath("//div[@class='col subject-name']")
        suffix = [f"У РЕПЕТИТОРА (₽/{мин})", f"У УЧЕНИКА (₽/{мин})", f"ДИСТАНЦИОННО (₽/{мин})"]
        # Initialize methods of work
        methods = ["Работает дистанционно", "Принимает у себя", "Выезд к клиенту"]
        for met in methods:
            person_info[met] = ""
        for j, ser in enumerate(services):
            name = names[j].text
            prices = ser.find_elements_by_xpath("//div[@class='col price']")
            for i in range(j*3, (j+1)*3):
                price = re.sub(r"[― ]", "", prices[i].text)
                if(len(price)>0):
                    price = int(re.split(r"[тр]", price)[1])
                    person_info[methods[i%3]] = "+"
                person_info[f"{name} {suffix[i%3]}"] = price
        return person_info

    def write_json_file(self, cat_name: str, profi_data: list):
            """
            Prepares backup for parsed data
            """
            # restrain number of columns
            columns = list(profi_data[0].keys())
            for profi in profi_data[1:]:
                for key in profi.keys():
                    # Create limit for the number of columns to avoid "too many columns exception" in db
                    if (key not in columns and len(columns) <= 500):
                        columns.append(key)
            updated_profi_data = []
            for person in profi_data:
                new_person = {}
                for pair in person.items():
                    if(pair[0] in columns and len(pair[0]) < 64):
                        new_person.update({pair[0] : pair[1]})
                updated_profi_data.append(new_person)

            if not os.path.isdir("repetit_ru_json_data"):
                os.mkdir("repetit_ru_json_data")

            with open(f"repetit_ru_json_data\{cat_name}_data_file.json", "w") as write_file:
                json.dump(updated_profi_data, write_file)

    def parse(self):
        database = WriteToDatabase("config_repetit_ru.conf")
        database.create_base()
        # Start Webdriver with supressed logging
        options = webdriver.ChromeOptions() 
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        self.driver = webdriver.Chrome(options=options)
        # Get categories
        self.get_category_links()
        for category in self.link_list:
            cat_name = category.split('/')[-2]
            # Check if category is already parsed
            if(os.path.exists(f"repetit_ru_json_data\{cat_name}_data_file.json")):
                logger.warning(f"'{cat_name}' category is already parsed!")
                continue
            logger.info(f"Treating '{cat_name}' category")
            counter = 0
            person_info = []
            try:
                category_profiles = self.get_profiles_by_category(f'{category}')
                logger.info(f"Found {len(category_profiles)} profiles in '{cat_name}' category")
                for person_link in category_profiles:
                    person_info.append(self.get_person_info(person_link))
                    counter+=1
            except:
                logger.critical("Problems with Internet connection or Web driver occured!")
                logger.exception(f"Only {counter} profiles of '{cat_name}' category were parsed")
            self.cat_profiles_dict[cat_name] = person_info
            logger.info(f"'{cat_name}' category was parsed successfully!")
            self.write_json_file(cat_name, self.cat_profiles_dict[cat_name])
            logger.info(f'{cat_name}_data_file.json with parsed data was created successfully!')
            database.create_and_write_table(f'repetit_ru_json_data\{cat_name}_data_file.json')
        self.driver.quit()

    def test(self):
        logger.info("This is a test run for only yaponskiy-yazyk category")
        database = WriteToDatabase('config_repetit_ru.conf')
        database.create_base()
        # Start Webdriver with supressed logging
        options = webdriver.ChromeOptions() 
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        self.driver = webdriver.Chrome(options=options)
        counter = 0
        test_profis = []
        category_profiles = self.get_profiles_by_category(f'https://repetit.ru/repetitors/yaponskiy-yazyk/')
        logger.info(f'Found {len(category_profiles)} profiles in yaponskiy-yazyk category')
        for person_link in category_profiles:
            test_profis.append(self.get_person_info(person_link))
        self.write_json_file("yaponskiy-yazyk", test_profis)
        database.create_and_write_table("repetit_ru_json_data\yaponskiy-yazyk_data_file.json")
        self.driver.quit()


