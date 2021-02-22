#!/usr/bin/python

import re
import sys
import mimetypes
import argparse
import string
import ffmpeg

from pathlib import Path, PurePath
from abc import ABCMeta, abstractmethod
from guessit import guessit

file_organizers = dict()

class MetaDataExtractor:
    guessit_short_date_options = ['-Y', '--date-year-first', '-D', '--date-day-first']
    def generate_new_name_field(self, my_dict):
        def append(key):
            val = my_dict.get(key)
            return "" if val is None else "-" + val
        
        new_name = my_dict["title"]
        new_name += append("date")
        new_name += append("episode")
        new_name += append("episode_title")
        new_name += append("screen_size")
        my_dict.update({"new_name" : new_name})
        return new_name
        
    def get_new_name(self, file_path, suggested_name):
        res = dict()
        mime = mimetypes.guess_type(file_path)
        if mime[0] == None or mime[0].lower().find("video") == -1:
            res.update({"title": suggested_name})
            self.generate_new_name_field(res)
            return res
        guessit_res = self.guess_it(suggested_name)
        val = guessit_res.get("title")
        if val is None:
            sys.exit('Cannot extract title from "{0}"'.format(suggested_name))
        res.update({"title" : val});
        date_val = guessit_res.get("date")
        if not date_val is None:
            res.update({"date" : '{:%Y.%m.%d}'.format(date_val)})
        int_val = guessit_res.get("episode")
        if not int_val is None:
            res.update({"episode" : "E" + str(int_val)})
        val = guessit_res.get("episode_title")
        if not val is None:
            res.update({"episode_title" : val})
        else:
            val = guessit_res.get("alternative_title")
            if not val is None:
                res.update({"episode_title" : val})
        val = guessit_res.get("screen_size")
        if not val is None:
            res.update({"screen_size" : val})
        else:
            probe = ffmpeg.probe(file_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            height = int(video_stream['height'])
            res.update({"screen_size" : str(height) + "p"})
            
        self.generate_new_name_field(res)
        return res

    def guess_it(self, query_str):
        match = re.search('\d\d.\d\d.\d\d', query_str) 
        short_date = not match is None
        if short_date and (args.guessit_options is None or  all(args.guessit_options.find(opt) == -1 for opt in self.guessit_short_date_options)):
            print("""Short date detected in "{0}".
            Please use short date options in guess it for avoiding ambiguity. Run guessit --help
            for more information.""".format(query_str))
            sys.exit(1)
        if any(args.guessit_options.find(opt) != -1 for opt in ["-t", "--type"]):
            sys.exit("You cannot use -t or --type for GuessIt!")
        return guessit(query_str, args.guessit_options + " -t movie")

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
                if not args.dry_run:
                    my_file.rename(target_file)
                print('Removing "{0}"'.format(my_dir))
                if not args.dry_run:
                    my_dir.rmdir()
    
    def description(self):
        return """
        If a directory has only just one file we move that file one
        level up and then remove that directory
        """
    
class RenameFile(FileOrganizer):
    
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
            if not self.is_current_file_name_valid_for_rename(old_file):
                print('Skipping "{0}"'.format(current_name))
                continue
            dir_name = old_file.parent.name
            new_name = self.extract_file_name(old_file, dir_name) + old_file.suffix
            print('Converting "{0}" to "{1}" using directory name "{2}"'.format(current_name, new_name, dir_name))
            new_file = old_file.with_name(new_name)
            if not args.dry_run:
                file_path.rename(new_file)
                
    @abstractmethod
    def is_current_file_name_valid_for_rename(self, current_file_name):
        pass
    
    # You can use your magic here! You get the directory name and you can extract suitable name from it
    @abstractmethod
    def extract_file_name(self, file_path, dir_name):
        pass

    
    
class HexOfbfuscated(RenameFile):
    
    def __init__(self):
        self.cache = dict()
        self.meta_data_extractor = MetaDataExtractor()
    
    def is_current_file_name_valid_for_rename(self, current_file_name):
        stem = current_file_name.stem
        return True if args.force else all(c in string.hexdigits for c in stem)
    
    def extract_file_name(self, file_path, dir_name):
        res = self.meta_data_extractor.get_new_name(file_path, dir_name)
        return res["new_name"]
    
    def description(self):
        return """
        If the file is obfuscated in hexadecimal but its parent directory has the
        correct name, this file organizer use that directory name to find a suitable
        name for the file. It relies on GuessIt that you can get following this link:
        https://guessit.readthedocs.io/en/latest/
        """
        
def register_file_organizers():
    file_organizers["hex_obfuscated"] = HexOfbfuscated()
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
    parser.add_argument("-f", "--force", action="store_true", help="Force to apply file organizer even though the file is not in the scope")
    parser.add_argument("-l", "--list", action="store_true", help="List of supported file organizers")
    parser.add_argument("-g", "--guessit-options", dest="guessit_options", default=None, help="Options for passing to guessit. e.g. -g'-Y -t episode'")
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
