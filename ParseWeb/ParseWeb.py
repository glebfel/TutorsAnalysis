import re
import os
import json
import string
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from WriteToDatabase import WriteToDatabase

module_logger = logging.getLogger("ParseWeb.ParseWeb")

class ProfiParser():

    MAIN_URL = "https://profi.ru/services/repetitor/"
    profile_suffix = r'?seamless=1&tabName=PROFILES'
    rate_list = ['Оценка 5', 'Оценка 4', 'Оценка 3', 'Оценка 2', 'Оценка 1']
    other_links_dict = {'Другие языки': 'languages',
                        'Интеллектуальные игры': 'int_games',
                        'Подготовка к экзаменам': 'exams'}
    
    def __init__(self):
        """
        Class constructor
        """
        self.link_list = []
        self.others_links = []
        self.cat_profiles_dict = {}

    def write_json_backup(self, cat_name: str, data: list):
        """
        Prepares backup for parsed data
        """
        if not os.path.isdir("json_data"):
            os.mkdir("json_data")

        with open(f"json_data\{cat_name}_data_file.json", "w") as write_file:
            json.dump(data, write_file)

    def get_cat_links(self):
        """
        Gets categories and their links for later parsing
        """
        logger = logging.getLogger("ParseWeb.ParseWeb.get_cat_links")
        logger.info("Gathering category list...")

        category_link = "services-catalog__column-title ui-link _t37mbJS _2fIr6we _2l1CpUa"
        self.driver.get(self.MAIN_URL)
        categories = self.driver.find_elements_by_class_name("services-catalog__content")
        elems = categories[0].find_elements_by_xpath("//a[@class]")
        search_cat = True
        # Compose two links lists: for subject categories, and for generic categories
        for i, elem in enumerate(elems):
            if elem.get_attribute("class") == category_link:
                if elem.get_attribute("href")[-1] == "#":
                    subject = " ".join(elem.text.split()[:-1])
                    self.others_links.append([self.other_links_dict[subject]])
                    search_cat = False
                else:
                    self.link_list.append(elem.get_attribute("href"))
                    search_cat = True
            elif not search_cat:
                self.others_links[-1].append(elem.text)
        # Move english category to the end because it is the largest one
        self.link_list.append(self.link_list.pop(self.link_list.index('https://profi.ru/repetitor/english/')))
        logger.info(f'--Found {len(self.link_list) + len(self.others_links)} categories')


    def get_person_info(self, link: str) -> dict:
        """
        Parses person by link and returns dictionary with reviews, education info, tution experience, prices, etc.
        """
        logger = logging.getLogger("ParseWeb.ParseWeb.get_person_info")
        self.driver.get(link)
        person_info = {}
        # Get person name
        person_info["Fullname"] = self.driver.find_element_by_xpath('//h1[@data-shmid="profilePrepName"]').text
        # Get education info
        try:
            personal_block = self.driver.find_element_by_xpath("//div[@class='_2iQ3do3']")
            if(personal_block.text.find("Образование") != -1):
                div_blocks = personal_block.find_elements_by_tag_name('div')
                # удаление лишних элементов из текста
                final_info = re.split(r"[,;1234567890()]", div_blocks[0].text)
                person_info["Образование"] =  final_info[0]
        # Get tution experience
            personal_block = personal_block.find_elements_by_tag_name('div')
            for block in enumerate(personal_block):
                text = block[1].text
                index = text.find('(')
                if(text.find("Репетиторский опыт") != -1 or text.find("Опыт репетиторства") != -1): 
                    if(index != -1):
                        years = text[index+1:index+3]
                        person_info["Репетиторский опыт (лет)"] =  years
                    else:
                        years = re.split(r"[(л–]", text)
                        person_info["Репетиторский опыт (лет)"] =  years[1]
                    break;
                elif (text.find("Репетиторская деятельность") != -1):
                    if(index != -1):
                        years = text[index+1:index+3]
                        person_info["Репетиторский опыт (лет)"] =  years
                    else:
                        years = re.split(r"[(гл–]", text)
                        person_info["Репетиторский опыт (лет)"] =  years[2]
                    break;
        except Exception as e:
            log.exception(e)
        # Get working methods
        methods_block = self.driver.find_element_by_xpath("//div[@class='_3z3XSoj']")

        if(methods_block.text.find("Работает дистанционно") != -1):
            person_info["Работает дистанционно"] =  "+"
        else:
            person_info["Работает дистанционно"] =  "-"
        if(methods_block.text.find("Принимает у себя") != -1):
            person_info["Принимает у себя"] =  "+"
        else:
            person_info["Принимает у себя"] =  "-"
        if(methods_block.text.find("Выезд к клиенту") != -1):
            person_info["Выезд к клиенту"] =  "+"
        else:
            person_info["Выезд к клиенту"] =  "-"
        # Get reviews
        reviews_block = self.driver.find_element_by_xpath('//div[@data-shmid="ProfileTabsBlock_bar"]')
        reviews = reviews_block.find_elements_by_tag_name('span')
        person_info["Количество оценок"] = int(reviews[0].text)
        if person_info["Количество оценок"] == 0:
            person_info["Средняя оценка"] = 0
            for i, rate in enumerate(self.rate_list):
                person_info[self.rate_list[i]] = 0
        else:
            person_info["Средняя оценка"] = float(reviews[1].text.replace(',', '.'))
            reviews_rates = self.driver.find_element_by_xpath('//div[@data-shmid="ReviewHistogramComponent"]')
            reviews_rates = reviews_rates.find_element_by_xpath('//div[@class="_2ZifqNc"]') \
                .find_elements_by_tag_name('div')
            for i, review in enumerate(reviews_rates):
                person_info[self.rate_list[i]] = int(review.text)
        # Get all services and prices
        try:
            price_button = self.driver.find_element_by_xpath('//a[@data-shmid="pricesMore"]')
            price_button.click()
        except:
            pass
        prices = self.driver.find_elements_by_xpath('//tr[@data-shmid="priceRow"]')
        for price in prices:
            columns = price.find_elements_by_tag_name('td')
            if columns[0].text:
                subj = columns[0].text.split("\n")[0].strip(".")
                price = columns[1].text.split(" ₽ / ")[0]
                person_info[subj] = price
        return person_info

    def get_profis_by_cat(self, cat_link: str):
        """
        Gets list of repetitors (or other profi) by category link
        """
        logger = logging.getLogger("ParseWeb.ParseWeb.get_profis_by_cat")
        self.driver.get(cat_link)
        # waiting for button to upload
        button = WebDriverWait(self.driver, 10).until(
        EC.presence_of_element_located((By.XPATH, '//a[@data-shmid="pagination_next"]')))
        while button:
            button.click()
            # waiting for page to upload
            try:
                button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//a[@data-shmid="pagination_next"]')))
            except:
                logger.info("End of category")
                button = False
        profiles = self.driver.find_elements_by_xpath('//a[@data-shmid="desktop-profile__avatar"]')
        profiles_links = [person.get_attribute("href") for person in profiles]
        return profiles_links

    def parse(self):
        """
        Parse all categories in JSON-files and MySQL database tables
        """
        logger = logging.getLogger("ParseWeb.ParseWeb.parse")
        database = WriteToDatabase()
        database.create_base()
        self.driver = webdriver.Chrome()
        # Get categories
        self.get_cat_links()
        # Treat general categories
        for category in self.link_list:
            cat_name = category.split('/')[-2]
            # check if categroy is already parsed
            if(os.path.exists(f"json_data\{cat_name}_data_file.json")):
                logger.warning(f'{cat_name} category is already parsed!')
                continue
            logger.info(f'Treating {cat_name} category')
            category_profiles = self.get_profis_by_cat(f'{category}{self.profile_suffix}')
            self.cat_profiles_dict[cat_name] = [self.get_person_info(person_link) for person_link in category_profiles]
            self.write_json_backup(cat_name, self.cat_profiles_dict[cat_name])
            database.create_and_write_table(cat_name, self.cat_profiles_dict[cat_name])
        # Treat generic categories
        for cat_list in self.others_links:
            cat_name = cat_list[0]
            logger.info(f'Treating {cat_name} category')
            for category in cat_list[1:]:
                category_profiles = self.get_profis_by_cat(f'{category}{self.profile_suffix}')
                self.cat_profiles_dict[cat_name] = [self.get_person_info(person_link) for person_link in
                                                    category_profiles]
                self.write_json_backup(cat_name, self.cat_profiles_dict[cat_name])
                database.create_and_write_table(cat_name, self.cat_profiles_dict[cat_name])
        self.driver.quit()

    def test(self):
        logger = logging.getLogger("ParseWeb.ParseWeb.test")
        logger.info("This is a test run for only hindi category")
        database = WriteToDatabase()
        database.create_base()
        self.driver = webdriver.Chrome()
        category_profiles = self.get_profis_by_cat(f'https://profi.ru/repetitor/hindi/{self.profile_suffix}')
        test_profis = [self.get_person_info(person_link) for person_link in category_profiles[:2]]
        self.write_json_backup("hindi", test_profis)
        database.create_and_write_table("hindi", test_profis)
        self.driver.quit()
