// PDF annotation helper functions
document.addEventListener('DOMContentLoaded', function() {
    // Function to capture selected text and position
    let selectedText = '';
    let selectionPosition = {};
    
    document.addEventListener('mouseup', function() {
        const selection = window.getSelection();
        selectedText = selection.toString().trim();
        
        if (selectedText && document.getElementById('pdf-container')) {
            const range = selection.getRangeAt(0);
            const rect = range.getBoundingClientRect();
            const pdfContainer = document.getElementById('pdf-container');
            const containerRect = pdfContainer.getBoundingClientRect();
            
            selectionPosition = {
                x: rect.left - containerRect.left,
                y: rect.top - containerRect.top,
                width: rect.width,
                height: rect.height,
                text: selectedText
            };
            
            // Update hidden input for position data
            const positionDataInput = document.getElementById('position_data');
            if (positionDataInput) {
                positionDataInput.value = JSON.stringify(selectionPosition);
            }
            
            // Show annotation tools
            showAnnotationTools(rect.left, rect.top + window.scrollY);
        } else {
            hideAnnotationTools();
        }
    });
    
    // Function to show annotation tools at position
    function showAnnotationTools(x, y) {
        const annotationTools = document.getElementById('annotation-tools');
        if (annotationTools) {
            annotationTools.style.display = 'block';
            annotationTools.style.left = `${x}px`;
            annotationTools.style.top = `${y + 20}px`;
        }
    }
    
    // Function to hide annotation tools
    function hideAnnotationTools() {
        const annotationTools = document.getElementById('annotation-tools');
        if (annotationTools) {
            annotationTools.style.display = 'none';
        }
    }
    
    // Add event listeners to annotation buttons
    document.querySelectorAll('.annotation-btn').forEach(button => {
        button.addEventListener('click', function() {
            const annotationType = this.dataset.type;
            createAnnotation(annotationType, selectionPosition);
            hideAnnotationTools();
        });
    });
    
    // Function to create annotation
    function createAnnotation(type, position) {
        if (!position.text) return;
        
        const annotation = {
            type: type,
            position: {
                x: position.x,
                y: position.y,
                width: position.width,
                height: position.height
            },
            text: position.text,
            comment: '',
            timestamp: new Date().toISOString()
        };
        
        // If it's a comment type, prompt for input
        if (type === 'comment') {
            const comment = prompt('Add your comment:', '');
            if (comment !== null) {
                annotation.comment = comment;
                saveAnnotation(annotation);
                renderAnnotation(annotation);
            }
        } else {
            saveAnnotation(annotation);
            renderAnnotation(annotation);
        }
    }
    
    // Function to save annotation
    function saveAnnotation(annotation) {
        // Get existing annotations or initialize empty array
        let annotations = JSON.parse(localStorage.getItem('pdf_annotations') || '[]');
        annotations.push(annotation);
        localStorage.setItem('pdf_annotations', JSON.stringify(annotations));
        
        // Also update hidden input for form submission if needed
        const annotationsInput = document.getElementById('annotations_data');
        if (annotationsInput) {
            annotationsInput.value = JSON.stringify(annotations);
        }
    }
    
    // Function to render annotation on the page
    function renderAnnotation(annotation) {
        const pdfContainer = document.getElementById('pdf-container');
        if (!pdfContainer) return;
        
        const annotationElement = document.createElement('div');
        annotationElement.className = `pdf-annotation pdf-annotation-${annotation.type}`;
        annotationElement.style.position = 'absolute';
        annotationElement.style.left = `${annotation.position.x}px`;
        annotationElement.style.top = `${annotation.position.y}px`;
        annotationElement.style.width = `${annotation.position.width}px`;
        annotationElement.style.height = `${annotation.position.height}px`;
        
        // Add tooltip with comment if available
        if (annotation.comment) {
            const tooltip = document.createElement('div');
            tooltip.className = 'annotation-tooltip';
            tooltip.textContent = annotation.comment;
            annotationElement.appendChild(tooltip);
            
            // Show tooltip on hover
            annotationElement.addEventListener('mouseover', function() {
                tooltip.style.display = 'block';
            });
            
            annotationElement.addEventListener('mouseout', function() {
                tooltip.style.display = 'none';
            });
        }
        
        pdfContainer.appendChild(annotationElement);
    }
    
    // Load and render existing annotations
    function loadAnnotations() {
        const annotations = JSON.parse(localStorage.getItem('pdf_annotations') || '[]');
        annotations.forEach(annotation => {
            renderAnnotation(annotation);
        });
    }
    
    // Call load annotations when page loads
    loadAnnotations();
    
    // Add clear annotations button functionality
    const clearButton = document.getElementById('clear-annotations');
    if (clearButton) {
        clearButton.addEventListener('click', function() {
            if (confirm('Are you sure you want to clear all annotations?')) {
                localStorage.removeItem('pdf_annotations');
                document.querySelectorAll('.pdf-annotation').forEach(el => el.remove());
                
                const annotationsInput = document.getElementById('annotations_data');
                if (annotationsInput) {
                    annotationsInput.value = '[]';
                }
            }
        });
    }
});