import logging
from ParseWeb import ProfiParser

if __name__ == '__main__':
    # create logger
    logger = logging.getLogger("ParseWeb")
    logger.setLevel(logging.INFO)
    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    # create the logging console handler
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(sh)
    
    logger.info("Strating servece...")
    Parser = ProfiParser()
    Parser.parse()
    logger.info("Stoping servece...")
