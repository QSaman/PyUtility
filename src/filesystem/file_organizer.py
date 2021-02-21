#!/usr/bin/python

import re
import sys
import mimetypes
import argparse

from pathlib import Path, PurePath
from abc import ABCMeta, abstractmethod

file_organizers = dict()

class FileOrganizer(metaclass=ABCMeta):
    @abstractmethod
    def organize_file(self, dir_path):
        pass
    
    @abstractmethod
    def description(self):
        pass

# If a directory has only just one file we move that file to ..
# and then remove that directory
class SingleFile(FileOrganizer):
    def organize_file(self, dir_path):
        dir_list = [my_dir for my_dir in dir_path.glob('**/*') if my_dir.is_dir()]
        for my_dir in dir_list:
            file_cnt = 0
            dir_cnt = 0
            my_file = None
            for file_object in my_dir.iterdir():
                if file_object.is_file():
                    file_cnt += 1
                    my_file = file_object
                elif file_object.is_dir():
                    dir_cnt += 1
            if file_cnt == 1 and dir_cnt == 0:
                pure = PurePath(my_file)
                target_dir = pure.parents[1]
                target_file = target_dir.joinpath(pure.name)
                if Path(target_file).exists():
                    print('"{0} exists. Aborting the operation"'.format(target_file))
                    sys.exit(1)
                print('Movig "{0}" to "{1}"'.format(pure, target_file))
                my_file.rename(target_file)
                print('Removing "{0}"'.format(my_dir))
                my_dir.rmdir()
    
    def description(self):
        return """
        If a directory has only just one file we move that file one
        level up and then remove that directory
        """
    
# This class rename the file with the name of it's parent directory
# You can extend this and use regex to extract some part of directory name
class RenameFileToParentDirectory(FileOrganizer):
    
    def organize_file(self, dir_path):
        def mime_filter(my_file):
            mime = mimetypes.guess_type(my_file)
            return False if mime[0] is None or mime[0].lower().find(args.mime.lower()) == -1 else True
        
        def no_filter(my_file):
            return True
        
        file_filter = mime_filter if args.mime else no_filter
        files = [my_file for my_file in dir_path.glob('**/*') if my_file.is_file() and file_filter(my_file)]
        
        for file_path in files:
            old_file = PurePath(file_path) 
            current_name = old_file.name
            dir_name = old_file.parent.name
            if (not self.validate_dir_name(dir_name)):
               sys.exit('directory name "{0}" doesn\'t match the regex'.format(dir_name))
            new_name = self.extract_file_name(dir_name) + old_file.suffix
            print('Converting "{0}" to "{1}" using directory name "{2}"'.format(current_name, new_name, dir_name))
            new_file = old_file.with_name(new_name)
            if not args.dry_run:
                file_path.rename(new_file)
    
    @abstractmethod
    def validate_dir_name(self, dir_name):
        pass
    
    @abstractmethod
    def extract_file_name(self, dir_name):
        pass
    
def register_file_organizers():
    file_organizers["single_file"] = SingleFile()
        
def main(argv):
    register_file_organizers()
    
    description = """
    Renaming files base on some criteria
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-o", "--file-organizer", dest="file_organizer", help="For a list of avaialbe organizer, run --list")
    parser.add_argument("-m", "--mime", help="Filter files based on this mime type (e.g. 'video')")
    parser.add_argument("-d", "--dry-run", dest="dry_run", action="store_true", help="It only show the operations without touching the file system")
    parser.add_argument("-l", "--list", action="store_true", help="List of supported file organizers")
    parser.add_argument("path", nargs='?', default=Path.cwd())
    global args
    args = parser.parse_args()
    
    if args.list:
        for key, value in file_organizers.items():
            print(key, ": ", value.description())
        sys.exit()
    if not args.file_organizer:
        print("You must use --file-organizer")
        sys.exit(1)
    if not args.file_organizer in file_organizers:
        print("Unsupported file organizer ", args.file_organizer)
        sys.exit(1)
            
    dir_path = Path(args.path)
    if not dir_path.exists():
        print('"{0}" doesn\'t exist'.format(args.path))
        sys.exit(1)
    if not dir_path.is_dir():
        print('"{0}" is not a directory'.format(args.path))
    
    organizer = file_organizers[args.file_organizer]
    organizer.organize_file(dir_path)

if __name__ == "__main__":
    main(sys.argv[1:])
