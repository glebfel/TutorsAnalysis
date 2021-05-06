import re
import os
import json
import string
import pymysql
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from WriteToDatabase import WriteToDatabase

module = logging.getLogger('ParseWeb.ParseWeb')

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
        self.logger = logging.getLogger("ParseWeb.ParseWeb.ProfiParser")

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

        if not os.path.isdir("json_data"):
            os.mkdir("json_data")

        with open(f"json_data\{cat_name}_data_file.json", "w") as write_file:
            json.dump(updated_profi_data, write_file)

    def get_category_links(self):
        """
        Gets categories and their links for later parsing
        """
        self.logger.info("Gathering category list...")
        try:
            category_link = "services-catalog__column-title ui-link _t37mbJS _2fIr6we _2l1CpUa"
            self.driver.get(self.MAIN_URL)
            categories = self.driver.find_elements_by_class_name("services-catalog__content")
            elems = categories[0].find_elements_by_xpath("//a[@class]")
        except:
            self.logger.critical("Problems with Internet connection or Web driver occured! Cannot gather category list!")
            return
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
        self.logger.info(f'Found {len(self.link_list) + len(self.others_links)} categories')

    def get_person_info(self, link: str) -> dict:
        """
        Parses person by link and returns dictionary with reviews, education info, tution experience, prices, etc.
        """
        self.driver.get(link)
        person_info = {}
        # Get person name
        person_info["Fullname"] = self.driver.find_element_by_xpath('//h1[@data-shmid="profilePrepName"]').text
        # Get education info
        personal_block = self.driver.find_element_by_xpath("//div[@class='_2iQ3do3']")
        if(personal_block.text.find("Образование") != -1):
            try:
                edu = self.driver.find_element_by_xpath("//div[@class='ui-text _3fhTO7m _3xKhc83 _2iyzK60 _1A6uUTD']")
                # Удаление лишних элементов 
                waste = self.driver.find_element_by_xpath("//span[@class='ui-text _TE8l15y _3xKhc83 _38NyyC- _32776-7']")
                edu = edu.text.replace(waste.text, '')
                person_info["Образование"] = re.split(r"[,;]", edu)[0]
            except:
                pass
        # Get tution experience
        personal_block = personal_block.find_elements_by_tag_name('div')
        for block in enumerate(personal_block):
            text = block[1].text
            index = text.find('(')
            try:
                if(text.find("Репетиторский опыт") != -1 or text.find("Опыт репетиторства") != -1): 
                    if(index != -1):
                        years = text[index+1:index+3]
                        person_info["Репетиторский опыт (лет)"] =  int(years)
                    else:
                        years = re.split(r"[(гл–]", text)
                        person_info["Репетиторский опыт (лет)"] =  int(years[1])
                    break;
                elif (text.find("Репетиторская деятельность") != -1):
                    if(index != -1):
                        years = text[index+1:index+3]
                        person_info["Репетиторский опыт (лет)"] =  int(years)
                    else:
                        years = re.split(r"[(гл–]", text)
                        person_info["Репетиторский опыт (лет)"] =  int(years[2])
                    break;
            except:
                pass
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
            try:
                person_info["Средняя оценка"] = float(reviews[1].text.replace(',', '.'))
                reviews_rates = self.driver.find_element_by_xpath('//div[@data-shmid="ReviewHistogramComponent"]')
                reviews_rates = reviews_rates.find_element_by_xpath('//div[@class="_2ZifqNc"]') \
                    .find_elements_by_tag_name('div')
                for i, review in enumerate(reviews_rates):
                    person_info[self.rate_list[i]] = int(review.text)
            except:
                pass

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
                subj = columns[0].text.split("\n")[0].strip(".") + " (₽/60 мин.)"
                price = columns[1].text.split("₽")[0]
                person_info[subj] = price
        return person_info

    def get_profiles_by_category(self, cat_link: str):
        """
        Gets list of repetitors (or other profi) by category link
        """
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
                self.logger.info("End of category")
                button = False
        profiles = self.driver.find_elements_by_xpath('//a[@data-shmid="desktop-profile__avatar"]')
        profiles_links = [person.get_attribute("href") for person in profiles]
        return profiles_links

    def parse(self):
        """
        Parse all categories in JSON-files and MySQL database tables
        """
        database = WriteToDatabase()
        database.create_base()
        # Start Webdriver with supressed logging
        options = webdriver.ChromeOptions() 
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        self.driver = webdriver.Chrome(options=options)
        # Get categories
        self.get_category_links()
        # Treat general categories
        for category in self.link_list:
            cat_name = category.split('/')[-2]
            # Check if category is already parsed
            if(os.path.exists(f"json_data\{cat_name}_data_file.json")):
                self.logger.warning(f"'{cat_name}' category is already parsed!")
                continue
            self.logger.info(f"Treating '{cat_name}' category")
            counter = 0
            person_info = []
            try:
                category_profiles = self.get_profiles_by_category(f'{category}{self.profile_suffix}')
                self.logger.info(f"Found {len(category_profiles)} profiles in '{cat_name}' category")
                for person_link in category_profiles:
                    person_info.append(self.get_person_info(person_link))
                    counter+=1
                    # print current state of the process
                    percentage = (counter/len(category_profiles))*100
                    if(percentage == 25):
                        self.logger.info("25% of category was already parsed!")
                    elif(percentage == 50):
                        self.logger.info("50% of category was already parsed!")
                    elif(percentage == 75):
                        self.logger.info("75% of category was already parsed!")
            except:
                self.logger.critical("Problems with Internet connection or Web driver occured!")
                self.logger.exception(f"Only {counter} profiles of '{cat_name}' category were parsed")
            self.cat_profiles_dict[cat_name] = person_info
            self.logger.info(f"'{cat_name}' category was parsed successfully!")
            self.write_json_file(cat_name, self.cat_profiles_dict[cat_name])
            self.logger.info(f'{cat_name}_data_file.json with parsed data was created successfully!')
            database.create_and_write_table(f'json_data\{cat_name}_data_file.json')
        # Treat generic categories
        for cat_list in self.others_links:
            cat_name = cat_list[0]
            # Check if categroy is already parsed
            if(os.path.exists(f"json_data\{cat_name}_data_file.json")):
                self.logger.warning(f"'{cat_name}' category is already parsed!")
                continue
            self.logger.info(f"Treating '{cat_name}' category")
            counter = 0
            person_info = []
            try:
                category_profiles = self.get_profiles_by_category(f'{category}{self.profile_suffix}')
                self.logger.info(f"Found {len(category_profiles)} profiles in '{cat_name}' category")
                for person_link in category_profiles:
                    person_info.append(self.get_person_info(person_link))
                    counter+=1
                    # print current state of the process
                    percentage = (counter/len(category_profiles))*100
                    if(percentage == 25):
                        self.logger.info("25% of category was already parsed!")
                    elif(percentage == 50):
                        self.logger.info("50% of category was already parsed!")
                    elif(percentage == 75):
                        self.logger.info("75% of category was already parsed!")
            except:
                self.logger.critical("Problems with Internet connection or Web driver occured!")
                self.logger.exception(f"Only {counter} profiles of '{cat_name}' category were parsed")
            self.cat_profiles_dict[cat_name] = person_info
            self.logger.info(f"'{cat_name}' category was parsed successfully!")
            self.write_json_file(cat_name, self.cat_profiles_dict[cat_name])
            self.logger.info(f'{cat_name}_data_file.json with parsed data was created successfully!')
            database.create_and_write_table(f'json_data\{cat_name}_data_file.json')
        self.driver.quit()

    def test(self):
        self.logger.info("This is a test run for only hindi category")
        database = WriteToDatabase()
        database.create_base()
        # Start Webdriver with supressed logging
        options = webdriver.ChromeOptions() 
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        self.driver = webdriver.Chrome(options=options)
        counter = 0
        test_profis = []
        try:
            category_profiles = self.get_profiles_by_category(f'https://profi.ru/repetitor/hindi/{self.profile_suffix}')
            self.logger.info(f'Found {len(category_profiles)} profiles in hindi category')
            for person_link in category_profiles:
                if(counter>30):
                    break;
                test_profis.append(self.get_person_info(person_link))
                counter+=1
                
        except:
            self.logger.critical("Problems with Internet connection or Web driver occured!")
            self.logger.exception(f"Only {counter} profiles of hindi category were parsed")
        self.write_json_file("hindi", test_profis)
        database.create_and_write_table("json_data\hindi_data_file.json")
        self.driver.quit()
