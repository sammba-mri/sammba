import json
import numpy as np
import os
import nibabel
from scipy import ndimage
from sklearn.datasets.base import Bunch
from nilearn import image
from nilearn.datasets.utils import _get_dataset_dir, _fetch_files
from .utils import _get_dataset_descr
from sammba.externals.nipype.utils.filemanip import fname_presuffix
from nilearn._utils.niimg_conversions import check_niimg
from nilearn._utils import niimg


def fetch_atlas_dorr_2008(image_format='nifti', downsample='30',
                          data_dir=None, url=None,
                          resume=True, verbose=1):
    """Download and load Dorr et al. atlas and average (dated 2008)

    Parameters
    ----------
    image_format : one of {'nifti', 'minc'}, optional
        Format to download

    downsample : one of {'30', '100'}, optional
        Downsampling resolution in microns.

    data_dir : str, optional
        Path of the data directory. Use to forec data storage in a non-
        standard location. Default: None (meaning: default)

    url: string, optional
        Download URL of the dataset. Overwrite the default URL.

    resume : bool
        whether to resumed download of a partly-downloaded file.

    verbose : int
        verbosity level (0 means no message).

    Returns
    -------
    data: sklearn.datasets.base.Bunch
        dictionary-like object, contains:

        - 't2' : str, path to nifti file containing the T2 weighted average.

        - 'maps' : str, path to nifti file containing regions definition.

        - 'names' : str list containing the names of the regions.

        - 'labels' : int list containing the label value of each region.

        - 'description' : description about the atlas and the template.

    References
    ----------

    A.E. Dorr, J.P. Lerch, S. Spring, N. Kabani and R.M. Henkelman. "High
    resolution three dimensional brain atlas using an average magnetic
    resonance image of 40 adult C57Bl/6j mice", NeuroImage 42(1):60-69, 2008.

    See http://www.mouseimaging.ca/research/mouse_atlas.html for more
    information on this parcellation.

    Licence: To be specified
    """
    if image_format not in ['nifti', 'minc']:
        raise ValueError("Images format must be 'nifti' or 'minc', you "
                         "entered {0}".format(image_format))

    if downsample not in ['30', '100']:
        raise ValueError("'downsample' must be '30' or '100', you "
                         "provided {0}".format(downsample))

    if url is None:
        if image_format == 'minc':
            url = ['http://www.mouseimaging.ca/mnc/C57Bl6j_mouse_atlas/',
                   'http://www.mouseimaging.ca/mnc/C57Bl6j_mouse_atlas/',
                   'http://www.mouseimaging.ca/research/C57Bl6j_mouse_atlas/']
        else:
            url = ['http://repo.mouseimaging.ca/repo/Dorr_2008_nifti/',
                   'http://repo.mouseimaging.ca/repo/Dorr_2008_nifti/',
                   'http://www.mouseimaging.ca/research/C57Bl6j_mouse_atlas/']

    if image_format == 'minc':
        files = ['male-female-mouse-atlas.mnc', 'c57_fixed_labels_resized.mnc',
                 'c57_brain_atlas_labels.csv']
    else:
        files = ['Dorr_2008_average.nii.gz', 'Dorr_2008_labels.nii.gz',
                 'c57_brain_atlas_labels.csv']

    files = [(f, u + f, {}) for f, u in zip(files, url)]

    dataset_name = 'dorr_2008'
    data_dir = _get_dataset_dir(dataset_name, data_dir=data_dir,
                                verbose=verbose)
    files_ = _fetch_files(data_dir, files, resume=resume,
                          verbose=verbose)

    fdescr = _get_dataset_descr(dataset_name)
    csv_data = np.recfromcsv(
        files_[2], skip_header=True,
        names=('roi_id', 'roi_label', 'right_index', 'left_index'))

    #TODO try dictionary with their region id as key and name as value
    left_rois = []
    right_rois = []
    lateral_rois = []
    for (idx, label, right_index, left_index) in csv_data:
        label = label.decode('UTF-8')  # for python3
        if right_index == left_index:
            lateral_rois.append((label, right_index))
        else:
            left_rois.append(('L {}'.format(label), left_index))
            right_rois.append(('R {}'.format(label), right_index))

    rois = lateral_rois + right_rois + left_rois
    labels, indices = map(list, zip(*rois))
    t2 = files_[0]
    maps = files_[1]
    if downsample == '100':
        t2_img = nibabel.load(t2)
        maps_img = check_niimg(maps, dtype=int)
        t2 = fname_presuffix(t2, suffix='_100um')
        maps = fname_presuffix(maps, suffix='_100um')
        if not os.path.isfile(t2):
            target_affine = np.eye(3) * .1
            t2_img = image.resample_img(t2_img, target_affine)
            t2_img.to_filename(t2)
        if not os.path.isfile(maps):
            maps_img = image.resample_img(maps_img, target_affine,
                                          interpolation='nearest')
            maps_img.to_filename(maps)

    params = dict(t2=t2, maps=maps,
                  names=np.array(labels)[np.argsort(indices)],
                  labels=np.sort(indices),
                  description=fdescr)

    return Bunch(**params)


def fetch_masks_dorr_2008(image_format='nifti', downsample='30',
                          data_dir=None, resume=True, verbose=1):
    """Downloads DORR 2008 atlas first, then uses its labels to produce tissue
    masks.

    Parameters
    ----------
    image_format : one of {'nifti', 'minc'}, optional
        Format to download

    downsample : one of {'30', '100'}, optional
        Downsampling resolution in microns.

    data_dir : str, optional
        Path of the data directory. Use to forec data storage in a non-
        standard location. Default: None (meaning: default)

    resume : bool, optional
        whether to resumed download of a partly-downloaded file.

    verbose : int, optional
        verbosity level (0 means no message).

    Returns
    -------
    mask_imgs: sklearn.datasets.base.Bunch
        dictionary-like object, contains:

        - 'brain' : nibabel.nifti1.Nifti1Image brain mask image.

        - 'gm' : nibabel.nifti1.Nifti1Image grey matter mask image.

        - 'cc' : nibabel.nifti1.Nifti1Image eroded corpus callosum image.

        - 'ventricles' : nibabel.nifti1.Nifti1Image eroded ventricles mask
        image.

    Notes
    -----
    This function relies on DORR 2008 atlas where we particularly pick
    ventricles and corpus callosum regions. Then, do a bit post processing
    such as binary closing operation to more compact brain and grey matter
    mask image and binary erosion to non-contaminated corpus callosum
    and ventricles mask images.
    Note: It is advised to check the mask images with your own data processing.

    See Also
    --------
    sammba.data_fetchers.fetch_atlas_dorr_2008: for details regarding
        the DORR 2008 atlas.
    """
    # Fetching DORR 2008 atlas
    dorr = fetch_atlas_dorr_2008(
        image_format=image_format, downsample=downsample, data_dir=data_dir,
        resume=resume, verbose=verbose)
    maps, names, labels = dorr['maps'], dorr['names'], dorr['labels']
    atlas_img = check_niimg(maps)
    atlas_data = niimg._safe_get_data(atlas_img).astype(int)

    brain_mask = (atlas_data > 0)
    brain_mask = ndimage.binary_closing(brain_mask, iterations=2)
    brain_mask_img = image.new_img_like(atlas_img, brain_mask)

    corpus_callosum_labels = labels[
        np.in1d(names.astype(str), ['R corpus callosum', 'L corpus callosum'])]
    print(np.in1d(names.astype(str), ['R corpus callosum', 'L corpus callosum']))
    print(corpus_callosum_labels)
    print(np.unique(atlas_data))
    corpus_callosum_mask = np.max(
        [atlas_data == value for value in corpus_callosum_labels], axis=0)
    eroded_corpus_callosum_mask = ndimage.binary_erosion(corpus_callosum_mask,
                                                         iterations=2)
    corpus_callosum_mask_img = image.new_img_like(atlas_img,
                                                  eroded_corpus_callosum_mask)

    ventricles_names = ['R lateral ventricle', 'L lateral ventricle',
                        'third ventricle', 'fourth ventricle']
    ventricles_labels = labels[np.in1d(names.astype(str), ventricles_names)]
    ventricles_mask = np.max(
        [atlas_data == value for value in ventricles_labels], axis=0)
    eroded_ventricles_mask = ndimage.binary_erosion(ventricles_mask,
                                                    iterations=2)
    ventricles_mask_img = image.new_img_like(atlas_img, eroded_ventricles_mask)

    gm_mask = (atlas_data > 0)
    gm_mask[ventricles_mask] = 0
    gm_mask[corpus_callosum_mask] = 0
    gm_mask = ndimage.binary_closing(gm_mask, iterations=2)
    gm_mask_img = image.new_img_like(atlas_img, gm_mask)

    mask_imgs = {'brain': brain_mask_img,
                 'gm': gm_mask_img,
                 'cc': corpus_callosum_mask_img,
                 'ventricles': ventricles_mask_img}

    return Bunch(**mask_imgs)


def fetch_atlas_waxholm_rat_2014(data_dir=None, url=None, resume=True,
                                 verbose=1, downsample='117',
                                 symmetric_split=False):
    """Download and load Pape et al. rat atlas (dated 2014), downsampled
       by the Scalable Brain Atlas.

    Parameters
    ----------
    data_dir : str, optional
        Path of the data directory. Use to forec data storage in a non-
        standard location. Default: None (meaning: default)

    downsample : one of {'78', '117', '200'}, optional
        Downsampling resolution in microns.

    url : string, optional
        Download URL of the dataset. Overwrite the default URL.

    resume : bool, optional
        Whether to resumed download of a partly-downloaded file.

    verbose : int, optional
        Verbosity level (0 means no message).

    Returns
    -------
    data: sklearn.datasets.base.Bunch
        dictionary-like object, contains:

        - 't2star': str, path to nifti file containing the averaged T2* images.

        - 'maps': str, path to nifti file containing regions definition.

        - 'labels': structured numpy.array containing the names of the regions
                    and their label values.

        - 'description': description about the atlas.

    References to cite
    ------------------
    The downsampled versions are provided by the Scalable Brain Atlas.
    The defining citations are

    Papp, Eszter A., Trygve B. Leergaard, Evan Calabrese, G. Allan Johnson,
    and Jan G. Bjaalie.
    `Waxholm Space atlas of the Sprague Dawley rat brain
     <http://dx.doi.org/10.1016/j.neuroimage.2014.04.001>`_
    NeuroImage 97 (2014): 374-86.

    Kjonigsen LJ, Lillehaug S, Bjaalie JG, Witter MP, Leergaard TB.
    `Waxholm Space atlas of the rat brain hippocampal region:
    Three-dimensional delineations based on magnetic resonance
    and diffusion tensor imaging.
    <http://dx.doi.org/10.1016/j.neuroimage.2014.12.080>`_
    NeuroImage 108 (2015):441-449

    Sergejeva M, Papp EA, Bakker R, Gaudnek MA, Okamura-Oho Y, Boline J,
    Bjaalie JG, Hess A. `Anatomical landmarks for registration of experimental
    image data to volumetric rodent brain atlasing templates.
    <http://dx.doi.org/10.1016/j.jneumeth.2014.11.005>`_
    Journal of Neuroscience Methods (2015) 240:161-169.

    See https://scalablebrainatlas.incf.org/rat/PLCJB14 for more
    information on this parcellation.

    Licence
    -------
    Creative Commons Attribution-NonCommercial-ShareAlike 4.0
    International
    """
    downsamples = ['78', '117', '200']
    if downsample not in downsamples:
        raise ValueError("'downsample' must be  one of {0}, you provided "
                         "{1}".format(downsamples, downsample))

    if downsample in ['78', '200']:
        downsample_version = '2'
    else:
        downsample_version = '3'

    if url is None:
        base_url = 'https://scalablebrainatlas.incf.org/'
        downsampled_atlas = 'WHS_SD_rat_atlas_v1.01_' +\
                            'downsample{0}.nii.gz'.format(downsample_version)
        downsampled_t2star = 'WHS_SD_rat_T2star_v1.01_' +\
                             'downsample{0}.nii.gz'.format(downsample_version)
        url = [base_url + 'templates/PLCJB14/source/' + downsampled_t2star,
               base_url + 'templates/PLCJB14/source/' + downsampled_atlas,
               base_url + 'services/labelmapper.php?' +
               'template=PLCJB14&to=acr&format=json']

    atlas_basename = 'WHS_SD_rat_atlas_v1_01_' +\
                     'downsample{0}.nii.gz'.format(downsample_version)
    t2star_basename = 'WHS_SD_rat_T2star_v1_01_' +\
                      'downsample{0}.nii.gz'.format(downsample_version)
    files = [t2star_basename, atlas_basename, 'WHS_SD_rat_labels.json']
    opts = [{'move': t2star_basename}, {'move': atlas_basename},
            {'move': 'WHS_SD_rat_labels.json'}]
    files = [(f, u, opt) for (f, u, opt) in zip(files, url, opts)]

    dataset_name = 'waxholm_rat_2014'
    data_dir = _get_dataset_dir(dataset_name, data_dir=data_dir,
                                verbose=verbose)
    files_ = _fetch_files(data_dir, files, resume=resume,
                          verbose=verbose)
    fdescr = _get_dataset_descr(dataset_name)

    # Return the json file contents as a dictionary
    with open(files_[2]) as json_data:
        json_rows = json.load(json_data)

    # Convert it to structured array
    names = ['value', 'name']
    formats = ['|S3', '|S59']
    dtype = dict(names=names, formats=formats)
    labels = np.array(list(json_rows.items()), dtype=dtype)

    # TODO: symmetric_split
    if symmetric_split:
        raise NotImplementedError('Not yet implemented')

    t2star = files_[0]
    maps = files_[1]
    if downsample == '200':
        t2star_img = nibabel.load(t2star)
        maps_img = nibabel.load(maps)
        t2star = t2star.replace('downsample2', '200um')
        maps = maps.replace('downsample2', '200um')
        if not os.path.isfile(t2star):
            target_affine = np.eye(3) * .2
            t2star_img = image.resample_img(t2star_img, target_affine)
            t2star_img.to_filename(t2star)
        if not os.path.isfile(maps):
            maps_img = image.resample_img(maps_img, target_affine,
                                          interpolation='nearest')
            maps_img.to_filename(maps)

    params = dict(t2star=t2star, maps=maps, labels=labels,
                  description=fdescr)

    return Bunch(**params)
