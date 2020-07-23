Dataset Formats
===

## Introduction
In the L5Kit codebase, we make use of a data format that consists of a set of [numpy structured arrays](https://docs.scipy.org/doc/numpy/user/basics.rec.html). Conceptually, it is similar to a set of CSV files with records and different columns, only that they are stored as binary files instead of text. Structured arrays can be directly memory mapped from disk.

### Interleaved data in structured arrays
Structured arrays are stored in memory in an interleaved format, this means that one "row" or "sample" is grouped together in memory. For example, if we are storing colors and whether we like them (as a boolean `l`), it would be `[r,g,b,l,r,g,b,l,r,g,b,l]` and not `[r,r,r,g,g,g,b,b,b,l,l,l]`). Most ML applications require row-based access - column-based operations are much less common - making this a good fit.

Here is how this example translates into code:

```python 
import numpy as np
my_arr = np.zeros(3, dtype=[("color", (np.uint8, 3)), ("label", np.bool)])

print(my_arr[0])
# ([0, 0, 0], False)
```

Let's add some data and see what the array looks like:

```python
my_arr[0]["color"] = [0, 218, 130]
my_arr[0]["label"] = True
my_arr[1]["color"] = [245, 59, 255]
my_arr[1]["label"] = True

print(my_arr["color"])
# array([([  0, 218, 130],  True), ([245,  59, 255],  True),
#        ([  0,   0,   0], False)],
#       dtype=[('color', 'u1', (3,)), ('label', '?')])

print(my_arr.tobytes())
# b'\x00\xda\x82\x01\xf5;\xff\x01\x00\x00\x00\x00')
```

As you can see, structured arrays allow us to mix different data types into a single array, and the byte representation lets us group samples together. Now imagine that we have such an array on disk with millions of values. Reading the first 100 values turns into a matter of reading the first 100*(3+1) bytes. If we had a separate array for each of the different fields we would have to read from 4 smaller files.

This becomes increasingly relevant with a larger number of fields and complexities of each field. In our dataset, an observation of another agent is described with its centroid (`dtype=(float64, 3)`), its rotation matrix (`dtype=(np.float64, (3,3))`), its extent or size (`dtype=(np.float64, 3)`) to name a few properties. Structured arrays are a great fit to group this data together in memory and on disk.

### Short introduction to zarr
We use the zarr data format to store and read these numpy structured arrays from disk. Zarr allows us to write very large (structured) arrays to disk in n-dimensional compressed chunks. See the [zarr docs](https://zarr.readthedocs.io/en/stable/). Here is a short tutorial:

```python
import zarr
import numpy as np

z = zarr.open("./path/to/dataset.zarr", mode="w", shape=(500,), dtype=np.float32, chunks=(100,))

# We can write to it by assigning to it. This gets persisted on disk.
z[0:150] = np.arange(150)
```

As we specified chunks to be of size 100, we just wrote to two separate chunks. On your filesystem in the `dataset.zarr` folder you will now find these two chunks. As we didn't completely fill the second chunk, those missing values will be set to the fill value (defaults to 0). The chunks are actually compressed on disk too! We can print some info:

```python
print(z.info)
# Type               : zarr.core.Array
# Data type          : float32
# Shape              : (500,)
# Chunk shape        : (100,)
# Order              : C
# Read-only          : False
# Compressor         : Blosc(cname='lz4', clevel=5, shuffle=SHUFFLE, blocksize=0)
# Store type         : zarr.storage.DirectoryStore
# No. bytes          : 2000 (2.0K)
# No. bytes stored   : 577
# Storage ratio      : 3.5
# Chunks initialized : 2/5
```

By not doing much work at all we saved almost 75% in disk space!

Reading from a zarr array is as easy as slicing from it like you would any numpy array. The return value is an ordinary numpy array. Zarr takes care of determining which chunks to read from.

```python
print(z[:10])
# [0. 1. 2. 3. 4. 5. 6. 7. 8. 9.]

print(z[::20]) # Read every 20th value
# [  0.  20.  40.  60.  80. 100. 120. 140.   0.   0.   0.   0.   0.   0.
#    0.   0.   0.   0.   0.   0.   0.   0.   0.   0.   0.]
```

Zarr supports StructuredArrays, the data format we use for our datasets are a set of structured arrays stored in zarr format.

Some other zarr benefits are:

* Safe to use in a multithreading or multiprocessing setup. Reading is entirely safe, for writing there are lock mechanisms built-in.
* If you have a dataset that is too large to fit in memory, loading a single sample becomes `my_sample = z[sample_index]` and you get compression out of the box.
* The blosc compressor is so fast that it is faster to read the compressed data and uncompress it than reading the uncompressed data from disk.
* Zarr supports multiple backend stores, your data could also live in a zip file, or even a remote server or S3 bucket.
* Other libraries such as xarray, Dask and TensorStore have good interoperability with Zarr.
* The metadata (e.g. dtype, chunk size, compression type) is stored inside the zarr dataset too. If one day you decide to change your chunk size, you can still read the older datasets without changing any code.

## 2020 Lyft Competition Dataset format
The 2020 Lyft competition dataset is stored in three structured arrays: `scenes`, `frames` and `agents`.

### Scenes
A scene is identified by the host (i.e. which car was used to collect it) and a start and end time. It consists of multiple frames (= discretized measurements), in the scene datatype we store the start and end index in the `frames` array described below that correspond to this scene.

```python
SCENE_DTYPE = [
    ("frame_index_interval", np.int64, (2,)),
    ("host", "<U16"),  # Unicode string up to 16 chars
    ("start_time", np.int64),
    ("end_time", np.int64),
]
```

### Frames
A frame consists of information about the ego vehicle (e.g. where it was at that time), a timestamp, and a reference to the agents in that frame. Because there may be multiple agents observed we store the start and the end index.

```python
FRAME_DTYPE = [
    ("timestamp", np.int64),
    ("agent_index_interval", np.int64, (2,)),
    ("ego_translation", np.float64, (3,)),
    ("ego_rotation", np.float64, (3, 3)),
]
```

### Agents
An agent is an observation by the AV of some other detected object. They each have a probability for each defined class associated with them, the possible labels are defined [here](https://github.com/lyft/l5kit/blob/master/l5kit/l5kit/data/zarr_dataset.py).

```python
AGENT_DTYPE = [
    ("centroid", np.float64, (2,)),
    ("extent", np.float32, (3,)),
    ("yaw", np.float32),
    ("velocity", np.float32, (2,)),
    ("track_id", np.uint64),
    ("label_probabilities", np.float32, (len(LABELS),)),
]
```
