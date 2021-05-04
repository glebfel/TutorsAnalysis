import logging
from ParseWeb import ProfiParser

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
    Parser = ProfiParser()
    Parser.test()
    logger.info("Stoping servece...")

if __name__ == '__main__':
    main()
