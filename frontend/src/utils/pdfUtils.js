import { getDocument } from 'pdfjs-dist';
import { GlobalWorkerOptions } from 'pdfjs-dist/build/pdf';

// Set up the worker
GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${getDocument.version}/pdf.worker.min.js`;
export class PdfParser {
    static async readPdf(file, onProgress) {
        const reader = new FileReader();
        
        return new Promise((resolve, reject) => {
            // Track file reading progress
            reader.onprogress = (event) => {
            if (event.lengthComputable) {
                const progress = Math.round((event.loaded / event.total) * 100);
                onProgress?.({ 
                stage: 'reading',
                progress 
                });
            }
            };

            reader.onload = async (event) => {
            try {
                const arrayBuffer = event.target.result;
                
                // Start loading PDF
                onProgress?.({ stage: 'loading', progress: 0 });
                const loadingTask = getDocument(arrayBuffer);
                
                // Track PDF loading progress
                loadingTask.onProgress = ({ loaded, total }) => {
                const progress = Math.round((loaded / total) * 100);
                onProgress?.({ 
                    stage: 'loading',
                    progress
                });
                };

                const pdf = await loadingTask.promise;
                const numPages = pdf.numPages;
                let pdfText = "";

                // Track page extraction progress
                for (let i = 1; i <= numPages; i++) {
                onProgress?.({ 
                    stage: 'extracting',
                    progress: Math.round((i - 1) / numPages * 100),
                    currentPage: i,
                    totalPages: numPages
                });

                const page = await pdf.getPage(i);
                const textContent = await page.getTextContent();
                const pageText = textContent.items
                    .map((item) => item.str)
                    .join(" ");
                pdfText += pageText + "\n";
                }

                // Signal completion
                onProgress?.({ 
                stage: 'complete',
                progress: 100
                });

                resolve(pdfText);
            } catch (error) {
                onProgress?.({ 
                stage: 'error',
                error: error.message 
                });
                reject(error);
            }
            };

            reader.onerror = (error) => {
            onProgress?.({ 
                stage: 'error',
                error: error.message 
            });
            reject(error);
            };

            // Start reading the file
            onProgress?.({ stage: 'reading', progress: 0 });
            reader.readAsArrayBuffer(file);
        });
    };
}