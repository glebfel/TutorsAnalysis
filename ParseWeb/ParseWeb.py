import re
import json
import string
import pymysql
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException


class ProfiParser():

    profile_suffix = r'?seamless=1&tabName=PROFILES'
    rate_list = ['FiveRate', 'FourRate', 'ThreeRate', 'TwoRate', 'OneRate']
    other_links_dict = {'Другие языки': 'languages',
                        'Интеллектуальные игры': 'int_games',
                        'Подготовка к экзаменам': 'exams'}

    
    def __init__(self, config_file: str = 'config.conf'):
        """
        Class constructor
        """
        self.link_list = []
        self.others_links = []
        self.cat_profiles_dict = {}
        self.conf_info = self.read_config(config_file)


    def read_config(self, config_file: str) -> dict:
        """
        Parses config file disposed in same folder as this script
        and returns search url and database info.
        """
        try:
            with open(config_file, 'r') as f:
                data = f.read().split('\n')
                conf_info = {line.split(': ')[0]: line.split(': ')[1] for line in data if line != ''}
                return conf_info
        except FileNotFoundError:
            print(f'Config file {config_file} is not found!')
            return {}


    def create_base(self):
        """
        Creates database if it does not exists
        """
        base_connector = pymysql.connect(host=self.conf_info['host'],
                                         user=self.conf_info['login'],
                                         password=self.conf_info['password'])
        try:
            base_connector.cursor().execute(f"create database {self.conf_info['database']}")
        except pymysql.ProgrammingError:
            print(f"Database with name {self.conf_info['database']} already exists")
            pass
        base_connector.close()


    def write_json_backup(self, cat_name: str, data: list):
        """
        Prepares backup for parsed data
        """
        with open(f"{cat_name}_data_file.json", "w") as write_file:
            json.dump(data, write_file)


    def create_and_write_table(self, table_name: str, profi_data: list):
        """
        Creates table for input category and writes data
        """
        base_connector = pymysql.connect(host=self.conf_info['host'],
                                         database=self.conf_info['database'],
                                         user=self.conf_info['login'],
                                         password=self.conf_info['password'])
        # Get list of columns for table
        columns = list(profi_data[0].keys())
        for profi in profi_data[1:]:
            for key in profi.keys():
                if key not in columns:
                    columns.append(key)
        # Create table and insert columns
        print(f"--Start writing table for {table_name}")
        column_insert = " TEXT, ".join([f"{column}" for column in columns])
        query_text = f'create table {table_name} ({column_insert} TEXT)'
        base_connector.cursor().execute(query_text)
        # Insert every person
        for person in profi_data:
            person_columns = list(person.keys())
            person_column_insert = ", ".join([f"{column}" for column in person_columns])
            person_values = list(person.values())
            person_values_insert = ", ".join([f"'{column}'" for column in person_values])
            person_query = f"insert into {table_name} ({person_column_insert}) values ({person_values_insert})"
            base_connector.cursor().execute(person_query)
            base_connector.commit()
        base_connector.cursor().close()
        print(f"--End of writing table for {table_name}")


    def get_cat_links(self):
        """
        Gets categories and their links for later parsing
        """
        print("--Gathering category list")
        category_link = "services-catalog__column-title ui-link _t37mbJS _2fIr6we _2l1CpUa"
        self.driver.get(self.conf_info['main_url'])
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
        print(f'--Found {len(self.link_list) + len(self.others_links)} categories')


    def get_person_info(self, link: str) -> dict:
        """
        Parses person by link and returns dictionary with reviews, education info, tution experience, prices, etc.
        """
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
                person_info["Education"] =  final_info[0]
        # Get tution experience
            personal_block = personal_block.find_elements_by_tag_name('div')
            for block in enumerate(personal_block):
                text = block[1].text
                index = text.find('(')
                if(text.find("Репетиторский опыт") != -1 or text.find("Опыт репетиторства") != -1): 
                    if(index != -1):
                        years = text[index+1:index+3]
                        person_info["Experience"] =  years
                    else:
                        years = re.split(r"[(л–]", text)
                        person_info["Experience"] =  years[1]
                    break;
                elif (text.find("Репетиторская деятельность") != -1):
                    if(index != -1):
                        years = text[index+1:index+3]
                        person_info["Experience"] =  years
                    else:
                        years = re.split(r"[(гл–]", text)
                        person_info["Experience"] =  years[2]
                    break;
        except Exception as e:
            print(e)
        # Get working methods
        methods_block = self.driver.find_element_by_xpath("//div[@class='_3z3XSoj']")

        if(methods_block.text.find("Работает дистанционно") != -1):
            person_info["Remote_work"] =  "+"
        else:
            person_info["Remote_work"] =  "-"
        if(methods_block.text.find("Принимает у себя") != -1):
            person_info["Hosts_work"] =  "+"
        else:
            person_info["Hosts_work"] =  "-"
        if(methods_block.text.find("Выезд к клиенту") != -1):
            person_info["Departure_to_the_client"] =  "+"
        else:
            person_info["Departure_to_the_client"] =  "-"

        # Get reviews
        reviews_block = self.driver.find_element_by_xpath('//div[@data-shmid="ProfileTabsBlock_bar"]')
        reviews = reviews_block.find_elements_by_tag_name('span')
        person_info["CountRates"] = int(reviews[0].text)
        if person_info["CountRates"] == 0:
            person_info["TotalRate"] = 0
            for i, rate in enumerate(self.rate_list):
                person_info[self.rate_list[i]] = 0
        else:
            person_info["TotalRate"] = float(reviews[1].text.replace(',', '.'))
            reviews_rates = self.driver.find_element_by_xpath('//div[@data-shmid="ReviewHistogramComponent"]')
            reviews_rates = reviews_rates.find_element_by_xpath('//div[@class="_2ZifqNc"]') \
                .find_elements_by_tag_name('div')
            for i, review in enumerate(reviews_rates):
                person_info[self.rate_list[i]] = int(review.text)
        # Get all services and prices
        try:
            price_button = self.driver.find_element_by_xpath('//a[@data-shmid="pricesMore"]')
            price_button.click()
            sleep(5)
        except:
            pass
        prices = self.driver.find_elements_by_xpath('//tr[@data-shmid="priceRow"]')
        for price in prices:
            columns = price.find_elements_by_tag_name('td')
            if columns[0].text:
                subj = re.sub(r" |-|\W", "_", columns[0].text.split("\n")[0]).strip(".")
                price = columns[1].text.split(" ₽ / ")[0]
                person_info[subj] = price
        return person_info


    def get_profis_by_cat(self, cat_link: str):
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
                print("End of category")
                button = False
        profiles = self.driver.find_elements_by_xpath('//a[@data-shmid="desktop-profile__avatar"]')
        profiles_links = [person.get_attribute("href") for person in profiles]
        return profiles_links


    def parse_info(self):
        self.create_base()
        self.driver = webdriver.Chrome()
        # Get categories
        self.get_cat_links()
        # Treat general categories
        for category in self.link_list:
            cat_name = category.split('/')[-2]
            print(f'--Treating {cat_name} category')
            category_profiles = self.get_profis_by_cat(f'{category}{self.profile_suffix}')
            self.cat_profiles_dict[cat_name] = [self.get_person_info(person_link) for person_link in category_profiles]
            self.write_json_backup(cat_name, self.cat_profiles_dict[cat_name])
            self.create_and_write_table(cat_name, self.cat_profiles_dict[cat_name])
        # Treat generic categories
        for cat_list in self.others_links:
            cat_name = cat_list[0]
            print(f'--Treating {cat_name} category')
            for category in cat_list[1:]:
                category_profiles = self.get_profis_by_cat(f'{category}{self.profile_suffix}')
                self.cat_profiles_dict[cat_name] = [self.get_person_info(person_link) for person_link in
                                                    category_profiles]
                self.write_json_backup(cat_name, self.cat_profiles_dict[cat_name])
                self.create_and_write_table(cat_name, self.cat_profiles_dict[cat_name])
        self.driver.quit()


    def test(self):
        print("--This is a test run for only hindi category")
        self.create_base()
        self.driver = webdriver.Chrome()
        category_profiles = self.get_profis_by_cat(f'https://profi.ru/repetitor/hindi/{self.profile_suffix}')
        test_profis = [self.get_person_info(person_link) for person_link in category_profiles]
        self.write_json_backup("hindi", test_profis)
        self.create_and_write_table("hindi", test_profis)
        self.driver.quit()

if __name__ == '__main__':
    Parser = ProfiParser()
    Parser.parse_info()
