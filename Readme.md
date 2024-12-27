# Eddy - AI-Augmented LaTeX Editor

Eddy is a work-in-progress AI-enhanced LaTeX text editor designed to elevate your document creation process. Inspired by tools like Overleaf, Eddy combines a sleek editing environment with powerful AI-driven features to simplify and accelerate your workflow. Whether you're drafting academic papers, reports, or other structured documents, Eddy offers robust tools for creating, organizing, and refining your content.

---

## Key Features

### 1. **Structure Templates**

- Reuse the organization of an existing document to create new work effortlessly.
- Upload a document—such as a journal article or a previous report—to generate a template for your project.

### 2. **Content Libraries**

- A Retrieval-Augmented Generation (RAG)-based context management system ensures AI interactions are grounded in factual, relevant information.
- Manage and organize factual content for seamless AI integration.

### 3. **Autocompletion**

- GitHub Copilot-style autocompletion for free text.
- Suggests contextually accurate snippets as you type, speeding up content creation.

### 4. **AI Chat Interface**

- Interact with an AI model capable of making intelligent edits to your main document.
- Review and accept or reject suggested diffs directly within the editor.
- Highlighted changes ensure clarity and easy integration of edits.

### 5. **Collaborative Work (Future Upgrade)**

- Enable real-time collaborative editing for team projects.

---

## Installation

Follow the steps below to set up Eddy on your local machine. Note that the backend currently uses textract, which does not run natively on Windows. Therefore, to run it on Windows, either find a way to install textract on Windows or run a docker image of the backend.

### Step 1: Set Up Node.js

1. Download and install **nvs** for Windows from [here](https://github.com/jasongin/nvs/releases), or for Linux follow the instructions from [here](https://github.com/jasongin/nvs).
2. For Windows: Add nvs to your system's PATH:
   - Go to **System Environment Variables** -> **Path** -> Add: `%LOCALAPPDATA%\Local\nvs`
3. Install **Node.js** using nvs:
   - Open a terminal and run: `nvs` and then select node version 23.4 or newer.
4. Install the required packages:
   - Open a terminal and run: `npm install` in the `AIEditor/frontend` folder.

### Step 2: Setup the Backend Environment

Create a new virtual environment and install the packages from the requirements.txt.
Also, the following dependencies OS are required:

**UbuntuDebian**
```bash
sudo apt-get install python3-dev libxml2-dev libxslt1-dev antiword unrtf poppler-utils tesseract-ocr \
flac ffmpeg lame libmad0 libsox-fmt-mp3 sox libjpeg-dev swig ghostscript pstotext
```

Next, install texlive for pandoc and then pandoc itself:
```bash
sudo apt-get install texlive pandoc
 ``

> Note: For Ubuntu 24.04, there is no recompiled pstotext available. Therefore, we need to build it from source.
> Install build dependencies:
> ```bash
> sudo apt install build-essential git devscripts dpkg-dev equivs
> ```
> Clone the code from the repository:
> `https://code.launchpad.net/~git-ubuntu-import/ubuntu/+source/pstotext/+git/pstotext/+ref/ubuntu/noble`
> Switch to the directory of pstotext
> Install the dependencies listed in the debian/control file of the package:
> ```bash
> sudo mk-build-deps -i
> ```
> Install the dependency package, for me this installed no packages:
> ```bash
> sudo apt install ./pstotext-build-deps_1.9-7_all.deb
> ```
> Install the tarball and place it in the parent directory of the pstotext directory:
> http://archive.ubuntu.com/ubuntu/pool/universe/p/pstotext/pstotext_1.9.orig.tar.gz
> Remove the dependency package pstotext-build-deps_1.9-7_all.deb
> Run the build (-us skips signing the source package, -uc skips signing the .changes file):
> ```bash
> dpkg-buildpackage -us -uc
> ```
> Switch to the parent directory of the pstotext directory and make the deb executable
> ```bash
> chmod u+x pstotext_1.9-7_amd64.deb
> ```
> Install the deb package:
> ```bash
> sudo apt install ./pstotext_1.9-7_amd64.deb
> ```

**MacOS**
```bash
brew cask install xquartz
brew install poppler antiword unrtf tesseract swig
```

Then, the backend server can be started by running the `app.py` script:

```bash
python app.py
```

### Step 3: Setup the Database

Make sure that docker is installed and then run:
```bash
docker pull pgvector/pgvector:0.8.0-pg17
docker run --name eddy_database -p 5432:5432 -e POSTGRES_PASSWORD=1234 -e PGDATA=/home/ruzickal/Code/Privat/AIEditor/backend/db -d pgvector/pgvector:0.8.0-pg17
```


> Old Version:
> ```bash
> docker pull postgres
> docker run --name eddy_database -p 5432:5432 -e POSTGRES_PASSWORD=1234 -e PGDATA=/> home/ruzickal/Code/Privat/AIEditor/backend/db -d postgres
>```

In the next step, we will create the right database, run this in a separate terminal while the container is running:

```bash
docker exec -it eddy_database psql -U postgres
create database eddy_db;
\c eddy_db;
CREATE EXTENSION vector;
```

## Setup from Scratch
NOTE!: This is not recommended and its only here for reference and keeping track of the initial setup.

### Step 1: Initialize the Frontend
1. Create the React app in the `AIEditor` folder by running:

```bash
npx create-react-app frontend
```

2. Install dependencies:

```bash
npm install react-quill @radix-ui/react-collapsible lucide-react --save
npm install react-router-dom --save
npm install react-confetti --save
npm install highlight.js --save
```

3. Set up TailwindCSS:

```bash
npm install -D tailwindcss
npx tailwindcss init
npm install tailwindcss-animate class-variance-authority clsx tailwind-merge lucide-react
npm install @radix-ui/react-icons
```

### Step 2: Configure TypeScript

1. Update the `tsconfig.json` file as follows:

```json
{
      "compilerOptions": {
         "baseUrl": ".",
         "paths": {
            "@/components": ["./src/components"],
            "@/components/*": ["./src/components/*"],
            "@/lib/*": ["./src/lib/*"],
            "@/*": ["./src/*"]
         }
      },
      "files": []
}
```

### Step 3: Install shadcn-ui Components

1. Initialize shadcn-ui and add components:

```bash
npx shadcn-ui@0.8.0 init
npx shadcn-ui@0.8.0 add button card menubar collapsible input label dialog alert
```

2. Update aliases in the `components.json` file to:

```json
"aliases": {
      "components": "src/components",
      "utils": "src/lib/utils"
}
```

3. Adjust imports in `.tsx` files (e.g., `button`) to use relative paths (`./...`) instead of `@/...`.



---

## Usage

### Backend

> Important Note: 
> In order to try the AI features, the debug flag in the `Config.py` file needs to be set to `True`. Otherwise, mockup models will generate the content used in debug mode.

1. Activate the virtual environment.
2. Run the backend using the `app.py` script:

```bash
python app.py
```

Make sure you have your gemini api key in your environment variables, named: `GEMINI_API_KEY` and other environment holding the secret key for token authentification in an environment variable called `EDDY_SECRET_KEY`

### Frontend

1. Select the appropriate Node.js version using nvs:

```bash
nvs
```


1. Switch to the `frontend` directory:

```bash
cd frontend
```

2. Start the frontend:

```bash
npm start
```

---

## Notes

### Development Hacks

#### Drop the Database

Drop and then recreate the database.

CAUTION! This of course deletes all the data! Only use in development.
```bash
docker exec -it eddy_database psql -U postgres
\c postgres;
drop database eddy_db;
create database eddy_db;
\c eddy_db;
CREATE EXTENSION vector;
```

## Contribution

We welcome contributions to Eddy! If you'd like to report an issue, suggest a feature, or contribute code, feel free to submit a pull request or open an issue in the repository.

### Development Setup

- Ensure you have the required dependencies installed.
- Follow the installation instructions above to set up the development environment.
- Use consistent code formatting and adhere to project standards.

---

## Future Goals

- **Enhanced Collaboration**: Introduce real-time collaboration features for seamless teamwork.
- **Improved AI Integration**: Expand AI capabilities for even more intelligent suggestions and content organization.
- **Custom Workflows**: Enable users to define and save custom workflows for recurring tasks.

---

Thank you for using Eddy! We’re excited to help you create beautiful LaTeX documents faster and smarter.