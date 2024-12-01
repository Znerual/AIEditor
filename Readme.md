# Installation
Installed nvs on Windows ([here](https://github.com/jasongin/nvs/releases)) to download node.js.
Very important! You need to add nvs to the path: Systemumgebungsvariablen -> Path -> Add: %LOCALAPPDATA%\Local\nvs

Then, npx can be used to create the react app, run the follwing in the AIEditor Folder:
```bash
npx create-react-app frontend
```

Install the dependencies:
```
npm install react-quill @radix-ui/react-collapsible lucide-react
```

Install things for frontend:
```bash
npm install -D tailwindcss
npx tailwindcss init
npm install tailwindcss-animate class-variance-authority clsx tailwind-merge lucide-react 
npm install @radix-ui/react-icons
```

Setup the tsconfig.json file and then run
```tconfig.json
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


```bash
npx shadcn-ui@0.8.0 init
npx shadcn-ui@0.8.0 add button card menubar collapsible
```

and also important is to change the aliases in the created components.json file.
Change them to 
```
  "aliases": {
    "components": "src/components",
    "utils": "src/lib/utils"
  }
```

and then in the .tsx files like button, change the @/.. to . .
# Usage

To use npm, first select the node.js version by running nvs in the terminal.