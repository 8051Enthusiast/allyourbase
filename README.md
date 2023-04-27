allyourbase
===========

`allyourbase.py` is a script that tries to find the base address of a firmware image by comparing the addresses of strings with the target addresses of all possible pointers, similar to [rbasefind](https://github.com/sgayou/rbasefind).

It works with arbritrary pointer sizes and endianness efficiently on decently sized firmware images (in the 10s of MBs, mostly limited by required RAM which grows linearly with filesize but has a high constant factor).

Example
-------
```
$ ./allyourbase.py -n 5 -l 8 -e little /usr/bin/ls
Found 630 strings
4/4
Offset: 0x11ffffefc0
```

Parameters
----------

```
-n N             the minimum length of strings to look for, in unicode codepoints
-l L             the length of pointers to look for, in bytes (4 = 32-bit pointers)
-e {little,big}  the endianness of the pointers
-a A             the alignment of the pointers (defaults to pointer lengths)
-f F             slack factor (higher = slower and more memory but more accurate)
```

How it works
------------
First, one finds all addresses where strings are at and puts them in a set.
Then one interpretes each (aligned) offset in the file as a pointer and puts the target addresses in a set.

Now the brute-force approach would be to try each base address and look at how many string offsets overlap the possible pointer target locations.
That way, one can simply choose the base address that has the highest overlap.

However that approach is not really usable on 64-bit address spaces without changes, and it quickly gets slower with more string addresses.

One useful realization is that "counting the overlap between to sets for each possible relative offset" is the same as doing the cross-correlation of the indicator vectors of the sets.
This can be efficiently implemented using the fast fourier transform by the convolution theorem.
Still you would have to do a fourier transform the size of the address space which in most cases is infeasable.

Instead, if the target addresses are reduced modulo n (bigger than filesize) one can do a circular cross-correlation of size n to find out the base address modulo n.
Doing that for a few coprime n until their product is bigger than the address space, one only has one solution that fits inside the address space which will probably be the base address.

Assuming the target addresses do not tend to differ by multiples of n, the matches of strings with errant pointers modulo n is modeled as binomial noise.
The purpose of the `-f` flag is to make the ratio of pointers in relation to n smaller so that the noise floor is lowered.

License
-------
This software is licensed under the MIT license.
