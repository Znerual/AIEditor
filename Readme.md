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

Follow the steps below to set up Eddy on your local machine.

### Step 1: Set Up Node.js

1. Download and install **nvs** for Windows from [here](https://github.com/jasongin/nvs/releases).
2. Add nvs to your system's PATH:
   - Go to **System Environment Variables** -> **Path** -> Add: `%LOCALAPPDATA%\Local\nvs`

### Step 2: Initialize the Frontend

1. Create the React app in the `AIEditor` folder by running:

   ```bash
   npx create-react-app frontend
   ```

2. Install dependencies:

   ```bash
   npm install react-quill @radix-ui/react-collapsible lucide-react --save
   npm install react-router-dom --save
   ```

3. Set up TailwindCSS:

   ```bash
   npm install -D tailwindcss
   npx tailwindcss init
   npm install tailwindcss-animate class-variance-authority clsx tailwind-merge lucide-react
   npm install @radix-ui/react-icons
   ```

### Step 3: Configure TypeScript

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

### Step 4: Install shadcn-ui Components

1. Initialize shadcn-ui and add components:

   ```bash
   npx shadcn-ui@0.8.0 init
   npx shadcn-ui@0.8.0 add button card menubar collapsible
   ```

2. Update aliases in the `components.json` file to:

   ```json
   "aliases": {
       "components": "src/components",
       "utils": "src/lib/utils"
   }
   ```

3. Adjust imports in `.tsx` files (e.g., `button`) to use relative paths (`./...`) instead of `@/...`.

### Step 5: Setup the Backend Environment

Create a new virtual environment and install the packages from the requirements.txt

### Step 6: Setup the Database

Make sure that docker is installed and then run:

```bash
docker pull postgres
docker run --name eddy_database -p 5432:5432 -e POSTGRES_PASSWORD=1234 -e PGDATA=D:\Code\Node.js\AIEditor\backend\db -d postgres
```

In the next step, we will create the right database:

```bash
docker exec -it eddy_database psql -U postgres
create database eddy_db;
```

---

## Usage

### Backend

1. Activate the virtual environment.
2. Run the backend using the `app.py` script:

   ```bash
   python app.py
   ```

### Frontend

1. Switch to the `frontend` directory:

   ```bash
   cd frontend
   ```

2. Start the frontend:

   ```bash
   npm start
   ```

### Node.js

1. Select the appropriate Node.js version using nvs:

   ```bash
   nvs
   ```

---

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