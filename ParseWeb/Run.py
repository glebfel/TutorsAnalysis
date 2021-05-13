import logging
from ProfiRuParser import ProfiRuParser
from RepetitRuParser import RepetitRuParser

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
    while(True):
        press = input()
        if (press == '1'):
            Parser = ProfiRuParser()
            Parser.parse()
            break;
        elif (press == '2'):
            Parser = RepetitRuParser()
            Parser.parse()
            break;
        else:
            print('Got wrong value. Please, type again...')
    logger.info("Stoping servece...")

if __name__ == '__main__':
    main()
