import pymysql

class WriteToDatabase():
    """Write JSON-file to database using MySQL"""
    def __init__(self, config_file: str = 'config.conf'):
        """
        Class constructor
        """
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
                if (key not in columns and len(columns) <= 500):
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

