import logging
from ParseWeb import ProfiParser
from ParseWeb import RepetitRuParser

def main():
    # create logger
    logger = logging.getLogger("ParseWeb")
    logger.setLevel(logging.INFO)
    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    # create the logging console handler
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(sh)
    # starting program
    logger.info("Strating servece...")
    print("Do you want to run profi.ru or repetit.ru parsing?\nPress '1' for profi.ru or '2' for repetit.ru...")
    press = input()
    if (press == 'p'):
        Parser = ProfiParser()
        Parser.parse()
    else:
        Parser = RepetitRuParser()
        Parser.parse()
    logger.info("Stoping servece...")

if __name__ == '__main__':
    main()
