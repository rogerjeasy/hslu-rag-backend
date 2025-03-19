# HSLU RAG Application - Backend

A Retrieval-Augmented Generation (RAG) application for HSLU MSc Students in Applied Information and Data Science to assist with exam preparation.

## System Architecture

This backend implements a RAG system using FastAPI, Firebase (Authentication and Firestore), and ChromaDB for vector storage. The architecture follows a layered approach:

1. **API Layer**: FastAPI endpoints for authentication, content management, and query processing
2. **Services Layer**: Business logic, Firebase integration, and RAG pipeline implementation
3. **RAG Components**: Document processing, text chunking, embedding generation, retrieval, and response generation
4. **Data Storage**: Firebase Firestore for user data and ChromaDB for vector embeddings

## Key Features

- Authentication with Firebase
- Course-specific question answering
- Exam preparation summaries
- Practice question generation
- Concept clarification with examples
- Knowledge gap identification

## Prerequisites

- Python 3.10+
- Docker and Docker Compose
- Firebase project with Authentication and Firestore enabled
- API keys for Claude or OpenAI

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/hslu-rag-backend.git
cd hslu-rag-backend
```

### 2. Create environment file

Copy the example environment file and update with your credentials:

```bash
cp .env.example .env
```

Edit `.env` to add your Firebase and LLM credentials.

### 3. Start with Docker Compose

```bash
docker-compose up -d
```

This will start the FastAPI application on port 8000 and Redis on port 6379.

### 4. Access the API documentation

Open your browser and navigate to:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Firebase Setup

1. Create a Firebase project at https://console.firebase.google.com/
2. Enable Authentication with Email/Password and Google sign-in
3. Create a Firestore database
4. Generate a service account key:
   - Go to Project Settings > Service Accounts
   - Click "Generate new private key"
   - Save the JSON file securely
5. Add the JSON content to your `.env` file (inside the FIREBASE_CREDENTIALS value)

## Development

### Run tests

```bash
docker-compose exec api pytest
```

### Format code

```bash
docker-compose exec api black .
docker-compose exec api isort .
```

### Lint code

```bash
docker-compose exec api flake8
```

## API Endpoints

### Authentication

- `POST /api/auth/register`: Register a new user
- `GET /api/auth/me`: Get current user profile
- `PUT /api/auth/me`: Update user profile
- `POST /api/auth/token/verify`: Verify authentication token

### Queries

- `POST /api/queries/`: Submit a new query
- `GET /api/queries/history`: Get query history
- `GET /api/queries/conversations`: Get all conversation IDs
- `DELETE /api/queries/history/{query_id}`: Delete a specific query

### Courses

- `GET /api/courses/`: Get all courses
- `GET /api/courses/{course_id}`: Get specific course details
- `POST /api/courses/{course_id}/enroll`: Enroll in a course

### Materials

- `POST /api/materials/`: Upload course material
- `GET /api/materials/{course_id}`: Get materials for a course

### Study Guides

- `POST /api/study-guides/`: Generate a study guide
- `GET /api/study-guides/`: Get all study guides

### Practice Questions

- `POST /api/practice/`: Generate practice questions
- `GET /api/practice/`: Get practice question sets

## Production Deployment

For production deployment:

1. Update CORS settings in `.env`
2. Set `ENV=production` in `.env`
3. Build the production Docker image:

```bash
docker build --target production -t hslu-rag-backend:production .
```

4. Deploy to your preferred container orchestration platform (Kubernetes, AWS ECS, etc.)

## License

[MIT License](LICENSE)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request