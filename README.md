# Hexpansion Firmwares

This repository manages the automatic update functionality for hexpansions at EMFCamp.

## For Hexpansion Creators

If you are creating a hexpansion that has electronic functionality, please consider adding an EEPROM of sufficient size to store a driver. Details of this are in the main badge documentation.

If you do have an EEPROM, you will need to programme it with a `vid` and a `pid` (vendor and product identifiers). These must be unique per type of hexpansion. Therefore, you will need to have values allocated for your hexpansion.

You can either get a `pid` in a shared vendor, or create your own vendor. If you intend to make limited different types of hexpansion, use a shared vendor. If you make lots of different types of hexpansion, create a new vendor.

### Getting a product identifier in a shared vendor

There are two generic vendor identifiers that are open to everyone. To get a `pid` assigned within one of these, go to https://github.com/emfcamp/hexpansion-firmwares/issues/new?template=product_id.yml and fill in the form. You will need to pick which vendor id you wish to use. `0xCAFE` is open to everyone. `0xF055` is for open-source hardware. You can then pick a 4 hex digit product identifier. Make sure this isn't already allocated.

Once you have done this, a pr will be automatically opened and merged to create the folder structure for you.

### Creating a new vendor

Go to https://github.com/emfcamp/hexpansion-firmwares/issues/new?template=vendor_id.yml and fill in the form. You can then pick a 4 hex digit vendor identifier. Make sure this isn't already allocated.

Once you have done this, a pr will be automatically opened and merged to create the folder structure for you.

#### Creating a product identifier if you have a vendor identifier

Once you have your own `vid`, you can assign `pid`s yourself. Just create a pull request to add a subfolder of your `vid`.

### Setting up a new hexpansion

Once you have a directory for your hexpansion, you will need to create an `eeprom.json` file. This specifies the contents of the header for the hexpansion, and matches what you would enter when provisioning through code.

For example:

    {
    "manifest_version": "2024",
    "fs_offset": 32,
    "eeprom_page_size": 32,
    "eeprom_total_size": 8192,
    "vid": "0xCAFE",
    "pid": "0x0101",
    "unique_id": 0,
    "friendly_name": "Example"
    }

You can also add Python files to populate the filesystem, in that directory.

**Note:** Please do not upload `.mpy` files that were generated with `mpy-cross`. Instead, create a file called `USE_MPY` in the directory, and all `.py` files will be automatically compiled to `.mpy` for you.

### Readme files

Each hexpansion can have a readme file. We recommend using this to link to your repositories or info on your hexpansion, and/or to document any information about the on-device driver you've written.

### Making changes

Once you have a vid or pid allocated, you can create pull requests to that directory. These will be automatically approved and merged.

If someone else creates a pull request, you will be pinged by a bot, and asked to approve them by commenting `/approve`. If you wish to allow other people to act on your behalf for your hexpansion, make a pull request to add them to `.github/CODEOWNERS`.

## For users of hexpansions

You generally will not need to interact with this repository, instead you can use the *Hexpansions* app on the badge to download updates.

If you have a hexpansion that you would like to make changes to, you should speak to the creator of the hexpansion. If you open a pull request against a hexpansion you didn't create, it will be flagged to the hexpansion creator for approval. The EMF Badge team will approve changes to hexpansion firmwares over the creator of the hexpansion.
