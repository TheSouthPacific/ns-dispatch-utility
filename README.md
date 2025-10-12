# NSDU - NationStates Dispatch Utility (In development)

NationStates Dispatch Utility (`nsdu`) is a small Python tool that helps you manage many dispatches via spreadsheets or text files and easily formats them in a consistent way. Here are the features:

- Update dispatches own by different nations at the same time.
- Load dispatch content and related configuration (e.g. title, category, owner nation) from files or Google Spreadsheets.
- Easily format dispatches according to a design guideline using a highly-customizable custom BBCode tag system.
- Use placeholders for information like government official names, links, WA nation number and put the real values inside files to change them on all dispatches in one-go.
- Jinja template engine allows you to control how placeholder values are printed out, reuse common dispatch elements via inheritance, procedurally generate your dispatch's fancy header/footer using macros instead of copy-and-paste, and more!
- Can be extended via plugins (using Pluggy).

## How to install

This tool is installed just like any other Python package:

1. Install Python (at least 3.13) [here](https://www.python.org/downloads/)
2. Download the package file [here](https://github.com/TheSouthPacific/ns-dispatch-utility/releases) (the one with the `.whl` in the name)
3. Open the command line, run `pip install <path to package file>` (e.g. `pip install ns_dispatch_utility-0.1.0-py3-none-any.whl`)
4. To upgrade, run `pip install --upgrade <path to new package file>`. To uninstall, run `pip uninstall ns-dispatch-utility`

A better approach is to install it in a virtual environment to isolate the tool and its libraries from other packages you've installed. **You should follow this way if you have already installed some other Python tools.**

1. Install uv [here](https://docs.astral.sh/uv/getting-started/installation/#__tabbed_1_2)
2. Download the package file [here](https://github.com/TheSouthPacific/ns-dispatch-utility/releases) (the one with the `.whl` in the name)
3. Open the command line, run `uv tool install <the path to the package file>` (e.g. `uv tool install ns_dispatch_utility-0.1.0-py3-none-any.whl`)
4. Repeat the above command with the newer package file to upgrade. Run `uv tool uninstall ns-dispatch-utility`.

## How it works

`nsdu` takes in the followings to update dispatches:

- **Dispatch config:** Things like title, category, subcategory, owner nation. Each dispatch also has a unique `name` to refer to it when using `nsdu`
- **Dispatch content:** To be more precise, these are templates containing placeholders, custom BBCode tags,... which are filled in with actual values when you run `nsdu` to produce the actual content that gets uploaded to NationStates.
- **Custom BBCode tags config**: Doing fancy text formatting requires you to write long sequences of NationStates BBCode tags. To avoid this, we can have custom BBCode tags which get expanded to actual NS BBCode tags by `nsdu`.
- **Placeholder variable values:** Specify the values to replace the placeholder variables in the dispatch templates (e.g. government official names).
- **Dispatch layouts**: A layout is something that contains the common elements of a dispatch such as header, footer. A dispatch template doesn't have to manually specify these elements, it can just uses an existing layout and only contain the stuff unique to it.
- **Macros, filters**: Specify how variables are converted into text (e.g. convert a government official variable into text with this format `[nation]Nation name[/nation] (@discord_username)`)

All of these information can be loaded from TOML files on your computer, in Google spreadsheets, or some other sources by "loader plugins" which you can select in the `nsdu` config file. Currently `nsdu` ships with these loaders:

- `google_dispatch_loader` to load dispatch config, content, layouts, and macros from Google spreadsheet, local TOML/plain text files.
- `file_template_var_loader` to load variable values from local TOML files.
- `file_simple_bbc_loader` to load custom BBCode tags config from local TOML files.

## How to setup and use

Open the command line, run `nsdu`. This will create a sample configuration file at the location shown on the output message. There are comments in it showing what each config option means. Edit the config to your liking. You must at least change these options:

- `user_agent`: Set the name of your main nation
- The loader options: Set the loaders you want to use (among the above values)
- Change the options about file paths or spreadsheets to point to the correct places.

Run `nsdu cred --add <nation name> <password>` to set password for the nations that own the dispatches you want to use `nsdu` on.

Run `nsdu update` to update all dispatches or `nsdu update <dispatch name(s)>` to update only some dispatches (e.g. `nsdu update welcome gov_intro card_guide`). The names here are the unique dispatch `name`s mentioned above

The following is an example of setting up `nsdu` to use Google spreadsheets to contain dispatch content and local TOML files to contain formatting config and placeholder variable values.

### Setup example: Use Google spreadsheets for dispatch content and local TOML files for formatting config and placeholder values

This example gives you something identical to [the South Pacific (TSP)'s dispatch system](https://www.nationstates.net/page=dispatch/id=1192500).

Create a Google spreadsheet with the same column setup as [the spreadsheet TSP is using](https://docs.google.com/spreadsheets/d/1c7rApk0yQp5b1S-kIPTj7n-ulbz2Yy5PKJjj6VzJnIE/edit?usp=sharing). To be quick, you should just duplicate the spreadsheet. This spreadsheet will contain your dispatch content and config with the following columns:

- **Name:** The unique name of a dispatch. When you run `nsdu update` command, you use this name to refer to the dispatch you want to update. Custom BBCode tags such as `[url][/url]` may receive this name instead of the full URL to link to a dispatch. In the spreadsheet, this column is also a clickable hyperlink to the actual dispatch in NationStates. You can edit the dispatch ID in the hyperlink to an existing dispatch to update something made manually on NS.
- **Action:** The action to perform on a dispatch when run `nsdu update`. Valid values are `create`, `edit`, `remove`. When you run the `nsdu update` command, the dispatch will be created, edited, or removed according to this value. If a dispatch is created or removed, the hyperlink in the name column is auto updated with the created dispatch's URL or is removed.
- **Owner nation:** The ID of the nation that owns a dispatch. Valid ID options are set in the `Owner nations` sheet of the master config spreadsheet.
- **Category setup:** The ID of the category setup a dispatch uses. A category setup is the combination of category and subcategory the dispatch has on NationStates. Valid ID options are set in the `Categories` sheet of the master config spreadsheet.
- **Template:** The content of the dispatch. To be more precise, this is a template which contains placeholders, custom BBCode tags,... which will be filled in with actual values when you run `nsdu update`.
- **Status:** The result of the `nsdu update` command after it acts on your dispatch. This column is auto-set by `nsdu` so don't touch it.

Create another Google spreadsheet with the same setup as [the spreadsheet TSP is using](https://docs.google.com/spreadsheets/d/1tdG_2Vp0VabvL9TGAaM5fX3vUrF-YLX8b851M1JgeJM/edit?usp=sharing). To be quick, you should just duplicate the spreadsheet. This one contains the layouts and macros (We'll call this the master config)
_TODO: Explaining about the columns of this_

Download [this](https://github.com/watarichanno/tsp_dispatches). These are TOML files which contain the placeholder values and custom BBCode tags. Change them to your preferences or don't touch them if you are updating TSP's dispatches.

Set the `nsdu` config file like [this example](). Change the `/path/to/folder/` part of all file `path` values to the folder containing the `tsp_dispatches` folder above.

Change the `spreadsheet_id` values to the spreadsheet ID of the Google spreadsheets you made. The ID is the bolded part of the spreadsheet's URL (in your browser URL bar when you view a spreadsheet): https://docs.google.com/spreadsheets/d/**1c7rApk0yQp5b1S-kIPTj7n-ulbz2Yy5PKJjj6VzJnIE**/edit

Get the `nsdu_google_creds.json` file which allows `nsdu` to edit the spreadsheets. _TODO: How to do this_
