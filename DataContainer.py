# data container for a sample


#### doc the logic of the code
# list all the data in ... should be one mode, not yet;
# access samples precisely with sample names is being implemented
# currently in v0:
# each time single sample was configured 
# in v1, things to be changed:
# - the raw data dir flatten
# - 561 channel no Emission wavelength (right now fill in dummy wavelength 000 so the reg expression works)


####
# to do in v2:  
# - consider the convenience & flexibility of batch processing in v2
# - enforce the implementation of only access from class attribute?
# - improve the summary function for better visualization and more informative
###
# !!!!!! NEED TO FIGURE OUT HOW TO MAKE VERSION DEPENDENT CODE 
# - for no idea which ver update
# - for ver updated known...
# future: may consider how this integrate with AIND pipeline (via nextflow)
# !!!!!! How the pipeline determined the states of the processing could be additional labor to pull up;
# - the path config. does not automatically create the path
# - where dv flag kicks in;
# - REPLACE ANY HARDCODE OF channel/laser to arg pass.
# ######

# ######
# how and when dirs get created may influence whether dir exists can be used as a check for the state of pipeline processing;
# => ??? makedirs & checkdirs should only happens inside each steps; then dc should only manipulate purely on path string level?
# ######
import json
import os
import re
import shutil
from typing import List
# manual config
class Datacontainer(): 
    """
    version v0;
    THIS IS PER SAMPLE ORGANIZATION... BATCH WITH PARALLEL SHOULD BE ADDITIONAL LAYER...
    Pend to have a concise explanation of:
    - assumed file structure 
        - (and how they depend with each other during manipulation, not urgent but important if you need to change the structure)
    - the logic of how data (in general, including all generated outout) are checked/accessed/created (kind of important)
    - ...
    """
    def __init__(self, scope, user, sample, imaging_direction, imaging_request, auto_laser, atlas_name, version='v0'):
        # ### meta data
        self.version = version # version check (see later)
        self.scope = scope.upper()
        if self.scope == 'SS':
            self.scope_name = "SmartSPIM"
        elif self.scope == 'LV':
            self.scope_name = "LaVision"
        else:
            raise(ValueError('scope can only be SS or LV, other not supported yet'))
        self.user = user
        self.sample = sample

        self.imaging_direction = imaging_direction.lower()
        assert self.imaging_direction in {'dv', 'vd'} 
        # dv means imaging from dorsal to ventral (going downwards), vice verse for vd (ventral upside downwards);

        self.imaging_request = str(imaging_request)

        ### paths config
        # 3 hardcoded root dir (by new design, pending fully implemented, should param in the end)
        self.raw_dir_root = '/jukebox/LightSheetData/_rawData' 
        self.process_dir_root = '/jukebox/LightSheetData/_procData' # pending
        self.viz_dir_root = '/jukebox/LightSheetData/neuroglancer/public/_ngviz' # pending

        self.raw_dir = self.get_raw_dir() # currently user based;
        self.process_dir = self.get_process_dir()
        self.viz_dir = self.get_viz_dir()

        # more detailed paths
        self.raw_channels = self.get_raw_channels()

        self.lasers = self.lasers # just to show this (first get values at get_raw_channels)
        self.auto_laser = auto_laser
        assert self.auto_laser in {488}, f'{self.auto_laser} is not supported yet; currently only 488 is supported'
        self.signal_lasers = self.get_signal_lasers(self.auto_laser) # keep some flexibility

        self.stitched_dir = self.get_stitched_dir()

        # atlas names
        self.atlas_name = atlas_name.lower()
        assert self.atlas_name in {'allen', 'pma', 'pra'}, f'check atlas_name, {self.atlas_name} is not supported' # pre-check if atlas is supported; include more later; 


        #### additional helper attributes
        self.label = self.get_label()

    ######################################################
    def get_raw_dir(self, verbose=True): 
        """raw data dir, to find single unique one
        syntax check hardcoded;
        ## 2 version of raw data organziation were implemented for the transition to new oranization
        - old (where we still separate LV and SS folders)
        - new (LV, SS folders will be identified with suffix in the end
        """
        
        # return a unique data dir;
        if self.version == 'v0':
            # proxy var. for compatibility
            dataRoot = os.path.join(self.raw_dir_root, self.scope_name, self.user)
        elif self.version == 'v1':
            dataRoot = os.path.join(self.raw_dir_root, self.user) # flattened
        dataDirs = self._listDir(dataRoot)
        # dataDirs = [i for i in os.listdir(os.path.join(self.raw_dir_root, self.scope_name, user)) if self._excludeCriteria(i)==False] # modify once _rawData dir flatten
        if verbose:
            # THIS SHOULD BE MOVED TO HIGHER LAYER OF BATCH PROCESSING #####!!######
            print(f'===data for user {self.user}, beginning ===/')
            print(*dataDirs, sep='\n')
            print(f'===data for user {self.user}, ending ======/')
        targetDir = [i for i in dataDirs if self.checkRawDataDirSyntax(i, debug=False)==True]
        if len(targetDir)==0:
            raise(Exception('dir not found, check if your target dir is named with correct syntax'))
        elif len(targetDir) >1:
            raise(Exception('dir found not unique with specifed condition'))
        else:
            pass
        
        return os.path.join(dataRoot, targetDir[0])
    
        
    def get_process_dir(self):
        """New proc dir""" 
        # process_dir = os.path.join(self.process_dir_root, user, os.path.basename(self.raw_dir)) # right now it fully matches the name;
        process_dir = os.path.join(self.process_dir_root, self.user, os.path.basename(self.raw_dir) + '-' + self.scope) # temporary solution for tell SS/LV data apart
        self._makeDirs(process_dir) # if exists, skip
        return process_dir
    
    def get_viz_dir(self):
        """New vizs dir""" 
        # viz_dir = os.path.join(self.viz_dir_root, user, os.path.basename(self.raw_dir)) # right now it fully matches the name;
        viz_dir = os.path.join(self.viz_dir_root, self.user, os.path.basename(self.raw_dir) + '-' + self.scope) # temporary solution for tell SS/LV data apart
        self._makeDirs(viz_dir) # if exists, skip
        return viz_dir

    # # other specific dirs under the 3 dir obtained will be hardcoded (since within these dir the file structure should stay the same unless subdir names change)
    def get_raw_channels(self):
        """
        Assume raw_folders has data for each channel placed in folders named in following convention:
        Ex_xxx_Em_yyy

        return a dict for path to raw data of each channel;

        """

        # Before need a hardcoded check for naming and supporting channels
        raw_channel_dirs_fp = self.raw_channel_inspection() # dirname based check

        self.lasers = self.get_lasers()
        raw_channels_dict = dict(zip(self.lasers, raw_channel_dirs_fp)) # should be sorted
        return raw_channels_dict

    def get_lasers(self):
        """
        This will be the key to call different directories of a given channel
        Dependent on get_raw_channels;
        First called in initialization by get_raw_channel after its inspection;
        stored as class attributes
        """
        raw_channel_dirs = [os.path.basename(i) for i in self.raw_channel_inspection(verbose=False)]
        lasers = [int(i[3:6]) for i in raw_channel_dirs] # get exictation wv length
        return lasers
    def get_signal_lasers(self, auto_laser: int) -> List[int]:
        """xclude the auto_laser defined from all lasers

        Args:
            auto_laser (int): specifify which channel is used as the template channel (in our case, we use AUTOfluorescence at 488)


        Returns:
            List[int]: list of lasers for signal channels
        """
        signal_lasers = [i for i in self.lasers if i!=auto_laser]
        return signal_lasers
    
    ################# processing dir (should be created for new data; should resume from different steps)
    ##### stitched 
    def get_stitched_dir(self, make_dirs=False):
        """
        create if not exists, return if exists?
        NOT CALLED in class initialization, explicitly called when used.
        Therefore, no return, write to class attribute
        """
        return self._getDirs_byChannel(parent_dir=self.process_dir, suffix='stitched',make_dirs=make_dirs)

    ##### destriped
    def get_destriped_dir(self, make_dirs=False):
        """
        create if not exists, return if exists?
        NOT CALLED in class initialization, explicitly called when used.
        Therefore, no return, write to class attribute
        """
        return self._getDirs_byChannel(parent_dir=self.process_dir, suffix='destriped', make_dirs=make_dirs)
    
    ##### downsized
    def get_downsized_dir(self, make_dirs=False):
        """
        create if not exists, return if exists?
        NOT CALLED in class initialization, explicitly called when used.
        Therefore, no return, write to class attribute
        """
        return self._getDirs_byChannel(parent_dir=self.process_dir, suffix='downsized', make_dirs=make_dirs)

    ##### registration
    def get_registration_dir(self, reg_type, make_dirs=False):
        # atlas to use?
        """
        create if not exists, return if exists?
        NOT CALLED in class initialization, explicitly called when used.
        Therefore, no return, write to class attribute
        SPECIF DIR NAME WAS HARDCODED ADAPTED FROM PREVIOUS PIPELINE FOR COMPATIBILITY !!!
        - (pending to change the lower level script in preivous pipeline) => for better self-explantory name to tell what does it mean for each mode;

        UPDATE: use this as a wrapper function to dispatch function calls
        """
        reg_type = reg_type.lower() # make it case insensitive
        assert reg_type in {'forward', 'inverse'}, "Registration type available are 'forward' and 'inverse', please double check"
        if reg_type == 'forward':
            # self.reg_dir_forward = self._getDirs_byChannel(parent_dir=self.process_dir, suffix='elastix', make_dirs=make_dirs)
            self.get_forward_registration_dir()
        elif reg_type == 'inverse':
            # self.reg_dir_inverse = self._getDirs_byChannel(parent_dir=self.process_dir, suffix='elastix_inverse_transform', make_dirs=make_dirs)
            self.get_inverse_registration_dir()

        # change later; add more depth dir if needed;

        ####### pending to fix this with RETURN VALUES
        
    def get_forward_registration_dirs(self, make_dirs=False) -> dict:
        """_summary_

        Args:
            make_dirs (bool, optional): _description_. Defaults to False.

        Returns:
            dict: dict of dirs
        """
        f_reg_dirs = {}
        f_reg_dirs['elastix'] = os.path.join(self.process_dir, 'elastix') # heritage vague naming (better way should be 'elastix_transform_for_forward_registration')
        f_reg_dirs['template_to_atlas'] = os.path.join(f_reg_dirs['elastix'], f'{self.auto_laser}_to_atl')
        dirname_per_channel = [os.path.join(f_reg_dirs['elastix'],f'{str(i)}_to_{self.auto_laser}') for i in self.signal_lasers]
        f_reg_dirs['signal_to_template'] = dict(zip(self.signal_lasers, dirname_per_channel))
        # include other params in other param based functions? or purely rely on script?
        return f_reg_dirs

    def get_inverse_registration_dirs(self, make_dirs=False) -> dict:
        """_summary_

        Args:
            make_dirs (bool, optional): _description_. Defaults to False.

        Returns:
            dict: dict of dirs
        """
        i_reg_dirs = {}
        i_reg_dirs['elastix'] = os.path.join(self.process_dir, 'elastix_inverse_transform') # heritage vague naming (better way should be 'elastix_transform_for_inverse_registration')
        i_reg_dirs['atlas_to_template'] = os.path.join(i_reg_dirs['elastix'], f'atl_to_{self.auto_laser}')
        dirname_per_channel = [os.path.join(i_reg_dirs['elastix'],f'{self.auto_laser}_to_{str(i)}') for i in self.signal_lasers]
        i_reg_dirs['template_to_signal'] = dict(zip(self.signal_lasers, dirname_per_channel))
        # include other params in other param based functions? or purely rely on script?
        return i_reg_dirs


    ##### (inverse reg. only) "raw_alas"
    def get_raw_atlas_dirs(self, make_dirs=False):
        # (pending to be checked) should receive some inputs from registration step;
        raw_atlas_dirs = {} 
        raw_atlas_dirs['output'] = os.path.join(self.raw_dir, 'raw_atlas')
        raw_atlas_dirs['atlas_to_template'] = self.get_inverse_registration_dirs()['atlas_to_template']
        raw_atlas_dirs['template_to_signal'] = self.get_inverse_registration_dirs()['template_to_signal']

        return raw_atlas_dirs


    ##### destripe first, directory collection
    def get_raw_tiles_dirs(self, inspect=False) -> dict:
        """a dict, each laser index a list of file dirs of tiles

        Args:
            inspect (bool, optional): _description_. Defaults to False.

        Returns:
            dict: _description_
        """
        raw_tile_dirs_dict = {}
        for l in self.lasers:
            tile_dirs = []
            dir_by_col = self.get_subdirs(self.raw_channels[l])
            dir_c_by_r = [tile_dirs.extend(self.get_subdirs(i)) for i in dir_by_col]
            if inspect:
                print('======= start of tiles_dirs ========')
                print(*tile_dirs, sep='\n')
                print('======= end of tiles_dirs ========')
            raw_tile_dirs_dict[l] = tile_dirs
        return raw_tile_dirs_dict
    
    def get_destriped_tiles_dirs(self, make_dirs=False) -> dict:
        destriped_tiles_dirs_dict = {}
        for l in self.lasers:
            # replace the part of string that points to raw tiles
            raw_string = self.raw_channels[l]
            destriped_string = f'{self.raw_channels[l]}_destriped_tiles'
            destriped_string = os.path.join(self.process_dir, f'{self.lasers}_destriped_tiles')
            destriped_tiles_dirs = [i.replace(raw_string, destriped_string) for i in self.get_raw_tiles_dirs[l]]
            destriped_tiles_dirs_dict[l] = destriped_tiles_dirs
        return destriped_tiles_dirs
        
        

    def get_subdirs(self, dir) -> List[str]:
        subdirs = sorted([os.path.join(dir,i) for i in os.listdir(dir)])
        return subdirs 


    ##### visualization with neuroglancer

    def get_ng_dirs(self, make_dirs=False):
        pass



    ##################################################### add more
    # # helper function: 
    # (need better group them in terms of:
    # - whether they are called directly or not 
    # - whether they are used only for specifc purposes
    # non specific use
    def _checkExists(self, path):
        return os.path.exists(path)
    def _makeDirs(self, path):
        os.makedirs(path, exist_ok=True)

    def _getDirs_byChannel(self, parent_dir, suffix, signal_only=False, make_dirs=False) -> dict:
        """_summary_

        Args:
            parent_dir (_type_): _description_
            suffix (_type_): _description_
            signal_only (bool, optional): whether populate dirs using signal lasers only (exclude auto_laser, which is the channel for template). Defaults to False.
            make_dirs (bool, optional): whether actually create the dirs. Defaults to False.

        Returns:
            dict: dirs with names
        """
        # print(parent_dir)
        # print(self.lasers)
        dirs_suffixed = [os.path.join(parent_dir, f"{str(i)}_{suffix}") for i in self.lasers]
        if make_dirs:
            [self._makeDirs(i) for i in dirs_suffixed] # as an alternaive to for loop
        d = dict(zip(self.lasers, dirs_suffixed))
        return d
    # # switch to _listDir(self, path); use this if the condition changes
    # def _excludeCriteria(self, path):
    #     """
    #     exclude string with some pattern, right now only for dir use
    #     return True if the criteria is met
    #     """
    #     exclude = path.startswith('.') and path.endswith('.db')
    #     return exclude
    def _clearDir(self, path):
        shutil.rmtree(path)
    
    def _listDir(self, path, ordered=True):
        """
        Modified ver of os.listdir, exclude unexpected dirs (sys dir, GUI generated dir)
        """
        subdirs = [i for i in os.listdir(path) if ((not i.startswith('.')) and (not i.endswith('.db')))]
        if ordered:
            subdirs = sorted(subdirs)
        return subdirs
    
    def _listDir_fp(self, path, ordered=True):
        """return full path; dependent on _listDir"""
        subdirs = self._listDir(path, ordered=ordered)
        subdirs_fp = [os.path.join(path, i) for i in subdirs]
        return subdirs_fp
    
    def _nested_dict_pretty(self, dict):
        return json.dumps(dict, indent=4) # for all the attributes

    
    # specific use
    def checkRawDataDirSyntax(self, dir, debug=False):
        substring = f"{self.user}-{self.sample}-{self.imaging_direction}-{self.imaging_request}"
        #################################################################################################################################################################################################################################
        ############### !!!!!!!!!!!!!!!!!!!!  NEED TO REWRITE THE SYNTAX: hyphen unavailable in saving option in SmartSPIM; MEANWHILE: BEWARE THAT PATH INTERPRETATION SHOULD BE ONLY DONE AT INITIALIZATION #####
        #################################################################################################################################################################################################################################
        # substring = f"{self.user}-{self.sample}-{self.imaging_direction}-{self.imaging_request}-{self.scope}" # TO BE IMPLEMENTNED
        if debug:
            print("====== start to debug ================")
            print(f'subtring to search: {substring}')
            print(f'dir to check: {dir}')
            print(f'substring is in dir? {substring in dir}')
            print("====== end debug =====================")
        return substring in dir
    
    def raw_channel_inspection(self, verbose=True):
        """
        Check the availability of raw data of each channel.
        method 1: reading the dirnames & get the availbility of channels; (only the syntax is specified)
        method 2: have a hardcoded channel list, compare the channels read from dirnames (exclude if not match...) 
        => implement method 1 first
        """
        # read the dir names first
        pattern = r"^Ex_\d{3}_Em_\d{3}$"
        # need to do the automatic conversion if the channel is still named in old convention 
        self.raw_channel_syntax_conversion()
        # print(self.raw_dir)
        subdirs = self._listDir(self.raw_dir) 
        # print(subdirs)
        raw_channel_dirs = [i for i in subdirs if re.match(pattern, i)]
        if verbose:
            print('raw channels found: ')
            print(*raw_channel_dirs, sep='\n')
        raw_channel_dirs_fp = [os.path.join(self.raw_dir,i) for i in raw_channel_dirs]
        return raw_channel_dirs_fp
    
    def raw_channel_syntax_conversion(self):
        """
        Old convention eg: Ex_xxx_Chy;
        # pattern_old = r"^Ex_\d{3}_Em_\d{3}$"
        A fixed dict for checking; {old: new}
        Check if there is raw channel named in old syntax;
        Convert syntax to new one: Ex_xxx_Em_yyy; see regexpression below
        # pattern_new = r"^Ex_\d{3}_Ch\d{1}$"
        - Rename the MIPs as well only in this step
        """
        subdirs = self._listDir(self.raw_dir)
        # print('debug')
        # print(subdirs)
        channel_dirs = [i for i in subdirs if re.match(r"^Ex_\d{3}_Ch\d{1}.*", i)] # to include MIPS as well
        dict = {"Ex_488_Ch0": "Ex_488_Em_525",
                "Ex_561_Ch1": "Ex_561_Em_000", # dummy Em, pending to fix
                "Ex_639_Ch2": "Ex_639_Em_690",
                "Ex_488_Ch0_MIP": "Ex_488_Em_525_MIP", # adding MIPs
                "Ex_561_Ch1_MIP": "Ex_561_Em_000_MIP", # dummy Em, pending to fix
                "Ex_639_Ch2_MIP": "Ex_639_Em_690_MIP"}
        
        # find and rename
        for c in channel_dirs:
            if c in dict.keys():
                old_name = os.path.join(self.raw_dir, c)
                new_name = os.path.join(self.raw_dir, dict[c])
                os.rename(old_name, new_name)
                print(f'rename {old_name} to {new_name}')

    ########    
    def summary(self):
        """To be implemented; simplest version, list all attributes"""
        print(f'========= start of summary of class, {self.version} ============')
        print(self._nested_dict_pretty(self.__dict__))
        print(f'========= end of summary of class, {self.version} ==============')

    def get_label(self) -> str:
        """return a short string that contains the necessary info. of a sample;
        Ideally, the dirname of each sample should be this.
        This may change as dev goes, therefore keep this function in case needs to be updated.

        Returns:
            str: the label of a sample; currently it is the dirname of each sample;
        """
        # print(f'========= start of short summary of class, {self.version} ============')
        # print out the string of the path
        print(self.raw_dir)
        label = os.path.basename(self.raw_dir)
        return label
        # print(f'========= end of short summary of class, {self.version} ==============')

        
            
if __name__ == '__main__':
    pass