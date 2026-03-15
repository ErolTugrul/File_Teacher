# File Teacher

The purpose of this project is to read, understand and answer questions about .pdf or .docx files the user has uploaded.
You can upload your files and ask specific questions about anything that is mentioned in your file.

The app is working on text-only files for now but i am intending to extend it's capabilities to work with the same
efficiency with tables, images and various file types in the future.

Before running this project:

1.Create a read token from Hugging Face

2.Set it as a Local environment variable

Windows:

```shell
setx HF_TOKEN "your_token_here"
```

Linux/Mac:

```shell
export HF_TOKEN="your_token_here"
```

## To Start

go to backend and run

```shell
cd backend
python -m uvicorn server:app
```

go to frontend and run

```shell
cd frontend
npm run dev

```
