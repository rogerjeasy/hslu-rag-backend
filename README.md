# HSLU RAG Application - Backend

A Retrieval-Augmented Generation (RAG) application for HSLU MSc Students in Applied Information and Data Science to assist with exam preparation.

## System Architecture

This backend implements a RAG system using **FastAPI**, **Firebase** (Authentication and Firestore), **Cloudinary** and **Pinecone** for vector storage. The architecture follows a layered approach:

1. **API Layer**: FastAPI endpoints for authentication, content management, and query processing
2. **Services Layer**: Application logic, Firebase integration, and RAG pipeline implementation
3. **RAG Components**: Document processing, text chunking, embedding generation, retrieval, and response generation
4. **Data Storage**: Firebase Firestore for user data, Cloudinary for course materials storage and Pinecone for vector embeddings

## Key Features
- **AI Study Assistant**: Get instant, accurate answers to your questions based on your specific HSLU course materials and textbooks.
- **Study Guide Generator**: Generate comprehensive study guides and concise summaries organized by importance and relevance to exams.
- **Practice Questions**: Test your knowledge with course-specific practice questions that reference specific lectures and concepts.
- **Authentication with Firebase** for secure user management and data storage.

<!-- - Concept clarification with examples
- Knowledge gap identification -->

## Prerequisites

- Python 3.10+
- Docker and Docker Compose
- Firebase project with Authentication and Firestore enabled (secret service account key)
- API keys for OpenAI

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/rogerjeasy/hslu-rag-backend.git
cd hslu-rag-backend
```

### 2. Create a `.env` File

Create a `.env` file in the root directory and add the following environment variables:

```env
FIREBASE_CREDENTIALS="your-path/your-secret-service-name.json"


# OpenAI settings
OPENAI_API_KEY="your-openai-api-key"

CLOUDINARY_CLOUD_NAME="your-cloudinary-cloud-name"
CLOUDINARY_API_KEY="your-cloudinary-api-key"
CLOUDINARY_API_SECRET="your-cloudinary-api-secret"
CLOUDINARY_URL="your-cloudinary-url"

PINECONE_AI_AGENT_API_KEY=your-pinecone-api-key
PINECONE_ENVIRONMENT=your-pinecone-environment
PINECONE_INDEX_NAME=your-pinecone-index-name
PINECONE_API_KEY=your-pinecone-api-key
CHUNK_SIZE=500
CHUNK_OVERLAP=100
```

### 3. Start The FastAPI Application

#### Using Docker Compose

```bash
docker-compose up -d
```

#### Using Uvicorn

```bash
uvicorn app.main:app --reload
```

#### Using Python

```bash
pip install -r requirements.txt
python -m app.main
```

This will start the FastAPI application on port 8000.

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
5. Add the JSON filename to your `.env` file (inside the FIREBASE_CREDENTIALS value)

## Key Components

The HSLU RAG Application architecture follows a layered approach with these key components:

### Document Processing Pipeline

- **DocumentProcessor**: Handles extraction of text from various file formats (PDF, PowerPoint, Jupyter notebooks, Word documents, code files). Key methods: `process_file()`, `_extract_text_from_pdf()`, `_extract_text_from_presentation()`.

- **EnhancedTextChunker**: Implements intelligent segmentation of course materials into semantic chunks with appropriate overlap for better context retrieval.

### Embedding and Retrieval System

- **EmbeddingService**: Manages vector embeddings creation and storage using OpenAI and Pinecone. Key methods: `create_embedding()`, `search_similar()`, `delete_by_metadata()`.

- **RAGRetriever**: Advanced document retriever with query enhancement and reranking capabilities. Methods include: `retrieve()`, `_semantic_reranking()`, `_expand_query()`.

### RAG Core Services

- **RAGService**: Orchestrates the RAG operations including context retrieval and response generation. Key methods: `retrieve_relevant_context()`, `generate_rag_response()`, `process_material()`.

- **RAGManager**: High-level service for managing user interactions with the RAG system. Key methods: `process_query()`, `generate_study_guide()`, `generate_practice_questions()`, `analyze_knowledge_gaps()`.

### LLM Integration

- **LLMService**: Handles integration with language models (OpenAI GPT, Claude) for response generation. Methods: `generate_response()`, `_generate_claude_response()`, `_generate_gpt_response()`.

## API Endpoints

### Authentication

- `POST /api/v1/auth/register`: Register a new user
- `GET /api/v1/auth/me`: Get current user profile
- `PUT /api/v1/auth/me`: Update user profile
- `POST /api/v1/auth/token/verify`: Verify authentication token


### Query RAG API Endpoints

Below are the available endpoints for the query RAG API:

BASE_URL: `/api/rag/v1`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/query` | Process a RAG query and return a contextualized response. |
| POST | `/query/conversation` | Process a RAG query, save it in a conversation, and return both the response and conversation. Creates a new conversation if conversation_id is not provided. |
| POST | `/study-guide` | Generate a study guide for a specific topic and save it to Firebase. |
| POST | `/study-guide/conversation` | Generate a study guide and save it in a conversation. Creates a new conversation if conversation_id is not provided. |
| POST | `/practice-questions` | Generate practice questions for a specific topic and save them to Firebase. |
| POST | `/practice-questions/conversation` | Generate practice questions and save them in a conversation. Creates a new conversation if conversation_id is not provided. |
| POST | `/knowledge-gap` | Analyze knowledge gaps based on a student query and save to Firebase. |
| POST | `/knowledge-gap/conversation` | Analyze knowledge gaps and save the analysis in a conversation. Creates a new conversation if conversation_id is not provided. |

### Course API Endpoints

Below are the available endpoints for the course API:
BASE_URL: `/api/v1`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/courses/` | Get a list of all courses available to the user. Requires authentication. |
| GET | `/courses/{course_id}` | Get details for a specific course. Requires authentication and course access. |
| POST | `/courses/` | Create a new course. Requires authentication. Only admins and instructors can create courses. |
| PUT | `/courses/{course_id}` | Update a course. Requires authentication. Only admins and the instructor who created the course can update it. |
| DELETE | `/courses/{course_id}` | Delete a course. Requires authentication. Only admins can delete courses. |
| POST | `/courses/{course_id}/enroll` | Enroll the current user in a course. Requires authentication. |
| POST | `/courses/{course_id}/unenroll` | Unenroll the current user from a course. Requires authentication. |

### Content API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/content/study-guides` | List study guides created by the current user. |
| GET | `/content/study-guides/{guide_id}` | Retrieve a specific study guide by ID. |
| DELETE | `/content/study-guides/{guide_id}` | Delete a specific study guide by ID. |
| GET | `/content/practice-questions` | List practice question sets created by the current user. |
| GET | `/content/practice-questions/{questions_id}` | Retrieve a specific practice question set by ID. |
| DELETE | `/content/practice-questions/{questions_id}` | Delete a specific practice question set by ID. |
| GET | `/content/knowledge-gaps` | List knowledge gap analyses created by the current user. |
| GET | `/content/knowledge-gaps/{gap_id}` | Retrieve a specific knowledge gap analysis by ID. |
| DELETE | `/content/knowledge-gaps/{gap_id}` | Delete a specific knowledge gap analysis by ID. |
| DELETE | `/content/user-content` | Delete all content created by the current user. |

### Materials

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/materials/upload` | Upload course materials to Cloudinary. |
| GET | `/materials/{material_id}` | Get course materials by ID. |
| DELETE | `/materials/{material_id}` | Delete course materials by ID. |
| GET | `/materials` | List all course materials. |

4. Deploy to your preferred container orchestration platform (Kubernetes, AWS ECS, etc.)

## License

[MIT License](LICENSE)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## Contributors

- Roger ([@rogerjeasy](https://github.com/rogerjeasy))
- Chichko ([@sahrabaettig](https://github.com/Riko20))