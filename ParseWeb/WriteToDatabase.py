import pymysql
import logging
import json

module = logging.getLogger('ParseWeb.WriteToDatabase')

class WriteToDatabase():
    """Write JSON-file to database using MySQL"""
    def __init__(self, config_file: str = 'config.conf'):
        """
        Class constructor
        """
        self.conf_info = self.read_config(config_file)
        self.logger = logging.getLogger("ParseWeb.WriteToDatabase.WriteToDatabase")

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
            self.logger.critical(f'Config file {config_file} is not found!')
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
            self.logger.warning(f"Database with name {self.conf_info['database']} already exists")
            pass
        base_connector.close()

    def create_and_write_table(self, file_name: str):
        """
        Creates table for input category and writes data
        """
        base_connector = pymysql.connect(host=self.conf_info['host'],
                                         database=self.conf_info['database'],
                                         user=self.conf_info['login'],
                                         password=self.conf_info['password'])
        # Read JSON-file
        profi_data= []
        with open(file_name) as json_file:
            profi_data = json.load(json_file)
        # Check if profi_data is empty
        if not profi_data:
            return
        # collect all columns 
        columns = list(profi_data[0].keys())
        for profi in profi_data[1:]:
            for key in profi.keys():
                if (key not in columns):
                    columns.append(key)
        # Create table name
        table_name = file_name.split('_')[1]
        table_name = table_name.split('\\')[1]
        # Create table and insert columns
        self.logger.info(f"Start writing table for '{table_name}' category...")
        column_insert = " TEXT, ".join([f"`{column}`" for column in columns])
        query_text = f'create table `{table_name}` ({column_insert} TEXT)'
        base_connector.cursor().execute(query_text)
        # Insert every person
        for person in profi_data:
            person_columns = list(person.keys())
            person_column_insert = ", ".join([f"`{column}`" for column in person_columns])
            person_values = list(person.values())
            person_values_insert = ", ".join([f"{base_connector.escape(value)}" for value in person_values])
            person_query = f"insert into `{table_name}` ({person_column_insert}) values ({person_values_insert})"
            base_connector.cursor().execute(person_query)
            base_connector.commit()
        base_connector.cursor().close()
        self.logger.info(f"End of writing table for '{table_name}' category...")

