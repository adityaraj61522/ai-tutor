// ============================================================
// AI-Tutor – Declarative Jenkins Pipeline
// ============================================================
// Stages
//   1. Checkout          – pull latest from SCM
//   2. Frontend – Lint   – eslint
//   3. Frontend – Test   – vitest
//   4. Build Images      – backend & frontend Docker images (parallel)
//   5. Push Images       – push to registry (only on main branch)
//   6. Deploy            – docker-compose up on the target host
// ============================================================

pipeline {

    // ── run on any available agent; swap to a label if you have dedicated nodes
    agent any

    // ── configuration ──────────────────────────────────────────────────────────
    environment {
        // Docker Hub (or any registry): set REGISTRY_CREDENTIALS in Jenkins
        // Credentials → Username/Password → id: "docker-registry-creds"
        REGISTRY          = "docker.io"                   // change to your registry
        REGISTRY_CREDS    = "docker-registry-creds"       // Jenkins credential id
        IMAGE_BACKEND     = "adityaraj61522/ai-tutor-backend"
        IMAGE_FRONTEND    = "adityaraj61522/ai-tutor-frontend"

        // Tag = short git commit SHA; falls back to "latest" when not in a git context
        IMAGE_TAG         = "${env.GIT_COMMIT ? env.GIT_COMMIT[0..6] : 'latest'}"

        // Backend build-arg (baked into frontend image at build time)
        VITE_BACKEND_URL  = "https://api-tutorai.aditya-raj.site"

        // SSH credential used for remote deployment (username + private-key)
        DEPLOY_SSH_CREDS  = "deploy-server-ssh"           // Jenkins credential id
        DEPLOY_HOST       = "your-server-ip-or-hostname"  // change to your server
        DEPLOY_USER       = "ubuntu"                      // change to your SSH user
        DEPLOY_DIR        = "/opt/ai-tutor"               // working dir on server
    }

    options {
        // Keep last 10 builds; discard older artifacts automatically
        buildDiscarder(logRotator(numToKeepStr: "10"))
        // Fail the build if it has been running for more than 30 minutes
        timeout(time: 30, unit: "MINUTES")
        // Do not allow concurrent builds of the same branch
        disableConcurrentBuilds()
        // Add timestamps to console output
        timestamps()
    }

    // ── pipeline stages ────────────────────────────────────────────────────────
    stages {

        // ------------------------------------------------------------------
        // 1. Checkout
        // ------------------------------------------------------------------
        stage("Checkout") {
            steps {
                checkout scm
                echo "Branch: ${env.BRANCH_NAME}  Commit: ${env.GIT_COMMIT}"
            }
        }

        // ------------------------------------------------------------------
        // 2. Frontend – Lint
        // ------------------------------------------------------------------
        stage("Frontend – Lint") {
            agent {
                docker {
                    image "node:20-alpine"
                    // reuse the workspace checked out by the outer agent
                    reuseNode true
                }
            }
            steps {
                dir("f-ai-tutor") {
                    sh "npm ci"
                    sh "npm run lint"
                }
            }
        }

        // ------------------------------------------------------------------
        // 3. Frontend – Test
        // ------------------------------------------------------------------
        stage("Frontend – Test") {
            agent {
                docker {
                    image "node:20-alpine"
                    reuseNode true
                }
            }
            steps {
                dir("f-ai-tutor") {
                    // deps already installed in lint stage; ci again in case of
                    // a fresh executor / separate workspace
                    sh "npm ci"
                    sh "npm test"
                }
            }
            post {
                always {
                    // Publish JUnit-compatible results when available
                    junit allowEmptyResults: true,
                          testResults: "f-ai-tutor/test-results/**/*.xml"
                }
            }
        }

        // ------------------------------------------------------------------
        // 4. Build Docker Images  (parallel)
        // ------------------------------------------------------------------
        stage("Build Images") {
            parallel {

                stage("Build – Backend") {
                    steps {
                        script {
                            docker.build(
                                "${IMAGE_BACKEND}:${IMAGE_TAG}",
                                "--file b-ai-tutor/server/Dockerfile b-ai-tutor/server"
                            )
                        }
                    }
                }

                stage("Build – Frontend") {
                    steps {
                        script {
                            docker.build(
                                "${IMAGE_FRONTEND}:${IMAGE_TAG}",
                                "--file f-ai-tutor/Dockerfile " +
                                "--build-arg VITE_BACKEND_URL=${VITE_BACKEND_URL} " +
                                "f-ai-tutor"
                            )
                        }
                    }
                }
            }
        }

        // ------------------------------------------------------------------
        // 5. Push Images  (main branch only)
        // ------------------------------------------------------------------
        stage("Push Images") {
            when {
                branch "main"
            }
            steps {
                script {
                    docker.withRegistry("https://${REGISTRY}", REGISTRY_CREDS) {
                        // push commit-sha tag
                        docker.image("${IMAGE_BACKEND}:${IMAGE_TAG}").push()
                        docker.image("${IMAGE_FRONTEND}:${IMAGE_TAG}").push()
                        // also update the :latest tag
                        docker.image("${IMAGE_BACKEND}:${IMAGE_TAG}").push("latest")
                        docker.image("${IMAGE_FRONTEND}:${IMAGE_TAG}").push("latest")
                    }
                }
            }
        }

        // ------------------------------------------------------------------
        // 6. Deploy  (main branch only)
        // ------------------------------------------------------------------
        stage("Deploy") {
            when {
                branch "main"
            }
            steps {
                sshagent(credentials: [DEPLOY_SSH_CREDS]) {
                    sh """
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_USER}@${DEPLOY_HOST} '
                            set -e
                            cd ${DEPLOY_DIR}

                            # Pull latest code
                            git pull origin main

                            # Pull freshly pushed images
                            docker pull ${IMAGE_BACKEND}:latest
                            docker pull ${IMAGE_FRONTEND}:latest

                            # Restart services with no downtime (rolling update)
                            docker compose pull
                            docker compose up -d --remove-orphans
                        '
                    """
                }
            }
        }
    }

    // ── post-build actions ──────────────────────────────────────────────────
    post {
        success {
            echo "Pipeline completed successfully. Tag: ${IMAGE_TAG}"
        }
        failure {
            echo "Pipeline FAILED. Check logs above."
            // Uncomment and configure to send email / Slack notifications:
            // mail to: "your-email@example.com",
            //      subject: "BUILD FAILED – AI-Tutor [${env.BRANCH_NAME}]",
            //      body: "See ${env.BUILD_URL}"
        }
        always {
            // Clean up dangling Docker images to keep the build node tidy
            sh "docker image prune -f || true"
        }
    }
}
