import { Button, Modal } from "react-bootstrap";
import { useState, useCallback, useRef } from "react";
import axios from "axios";
import { useDropzone, FileWithPath } from 'react-dropzone';
import { toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import styleUtils from "../styles/utils.module.css";

interface FileUploadDialogProps {
    onDismiss: () => void,
    onFilesUploaded: (files: File[]) => void,
    patientCNP: string,
    caller: string,
}

type FileWithRelativePath = FileWithPath & {
    webkitRelativePath?: string;
};

function getDisplayPath(file: FileWithRelativePath): string {
    return file.webkitRelativePath || file.path || file.name;
}

function isDicomFile(file: File): boolean {
    const name = file.name.toLowerCase();
    return name.endsWith('.dcm') || name.endsWith('.dicom');
}

async function readDirectoryEntries(entry: FileSystemDirectoryEntry): Promise<FileSystemEntry[]> {
    const reader = entry.createReader();
    const entries: FileSystemEntry[] = [];

    const readBatch = (): Promise<FileSystemEntry[]> =>
        new Promise((resolve, reject) => {
            reader.readEntries(resolve, reject);
        });

    let batch = await readBatch();
    while (batch.length > 0) {
        entries.push(...batch);
        batch = await readBatch();
    }

    return entries;
}

async function entryToFile(entry: FileSystemFileEntry, relativePath: string): Promise<FileWithRelativePath> {
    const file = await new Promise<File>((resolve, reject) => {
        entry.file(resolve, reject);
    });

    Object.defineProperty(file, 'webkitRelativePath', {
        value: relativePath,
        configurable: true,
    });

    return file as FileWithRelativePath;
}

async function traverseFileTree(entry: FileSystemEntry, pathPrefix = ''): Promise<FileWithRelativePath[]> {
    if (entry.isFile) {
        const relativePath = pathPrefix ? `${pathPrefix}/${entry.name}` : entry.name;
        return [await entryToFile(entry as FileSystemFileEntry, relativePath)];
    }

    if (!entry.isDirectory) {
        return [];
    }

    const directoryPath = pathPrefix ? `${pathPrefix}/${entry.name}` : entry.name;
    const children = await readDirectoryEntries(entry as FileSystemDirectoryEntry);
    const nestedFiles = await Promise.all(
        children.map((child) => traverseFileTree(child, directoryPath))
    );

    return nestedFiles.flat();
}

async function getFilesFromDataTransfer(dataTransfer: DataTransfer): Promise<FileWithRelativePath[]> {
    const items = dataTransfer.items;
    if (!items) {
        return Array.from(dataTransfer.files || []) as FileWithRelativePath[];
    }

    const entries = Array.from(items)
        .map((item) => item.webkitGetAsEntry())
        .filter((entry): entry is FileSystemEntry => entry !== null);

    const nestedFiles = await Promise.all(entries.map((entry) => traverseFileTree(entry)));
    return nestedFiles.flat();
}

const FileUploadDialog = ({ onDismiss, onFilesUploaded, patientCNP, caller }: FileUploadDialogProps) => {
    const [selectedFiles, setSelectedFiles] = useState<FileWithRelativePath[]>([]);
    const folderInputRef = useRef<HTMLInputElement>(null);

    const addFiles = useCallback((incomingFiles: FileWithRelativePath[]) => {
        const filteredFiles = caller === 'CT'
            ? incomingFiles.filter(isDicomFile)
            : incomingFiles;

        if (caller === 'CT' && incomingFiles.length > 0 && filteredFiles.length === 0) {
            toast.error('No DICOM (.dcm) files were found in the selection.');
            return;
        }

        setSelectedFiles((previousFiles) => {
            const existingPaths = new Set(previousFiles.map(getDisplayPath));
            const uniqueFiles = filteredFiles.filter((file) => !existingPaths.has(getDisplayPath(file)));
            return [...previousFiles, ...uniqueFiles];
        });
    }, [caller]);

    const onDrop = useCallback((acceptedFiles: FileWithRelativePath[]) => {
        addFiles(acceptedFiles);
    }, [addFiles]);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        getFilesFromEvent: async (event) => {
            if ('dataTransfer' in event && event.dataTransfer) {
                return getFilesFromDataTransfer(event.dataTransfer);
            }

            if ('target' in event && event.target instanceof HTMLInputElement && event.target.files) {
                return Array.from(event.target.files) as FileWithRelativePath[];
            }

            return [];
        },
        noClick: caller === 'CT',
        noKeyboard: caller === 'CT',
        disabled: caller === 'CT' && selectedFiles.length > 0,
    });

    const handleFolderSelection = (event: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(event.target.files || []) as FileWithRelativePath[];
        addFiles(files);
        event.target.value = '';
    };

    const handleFileUpload = async () => {
        const formData = new FormData();

        formData.append('uploadType', caller);
        formData.append('cnp', patientCNP);

        selectedFiles.forEach((file) => {
            const relativePath = getDisplayPath(file).replace(/\\/g, '/');
            formData.append('file', file, relativePath);
        });
        
        try {
            const response = await axios.post('/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            console.log(response.data);
            onFilesUploaded(selectedFiles);
            if (caller !== 'PDF') {
                toast.success("Upload successfully!");
            }
        } catch (error) {
            console.error('Error uploading files:', error);
            toast.error('Upload failed. Please try again.');
        }
    };

    const groupedFiles = selectedFiles.reduce<Record<string, FileWithRelativePath[]>>((groups, file) => {
        const displayPath = getDisplayPath(file);
        const folder = displayPath.includes('/')
            ? displayPath.slice(0, displayPath.lastIndexOf('/'))
            : '(root)';
        if (!groups[folder]) {
            groups[folder] = [];
        }
        groups[folder].push(file);
        return groups;
    }, {});

    return (
        <>
            <Modal show onHide={onDismiss} className={styleUtils.fileUploadDialog}>
                { caller === "CT" &&
                    <Modal.Header closeButton>
                        <Modal.Title>Add CT</Modal.Title>
                    </Modal.Header>
                }
                { caller === "PDF" &&
                    <Modal.Header closeButton>
                        <Modal.Title>Add pdf</Modal.Title>
                    </Modal.Header>
                }
                <Modal.Body>
                    {caller === "CT" ? (
                        <>
                            <p>Select a DICOM scan folder, or drag and drop a folder onto the area below.</p>
                            <div className="d-flex gap-2 mb-3">
                                <Button
                                    variant="outline-primary"
                                    onClick={() => folderInputRef.current?.click()}
                                >
                                    Select DICOM folder
                                </Button>
                                <Button
                                    variant="outline-secondary"
                                    onClick={() => setSelectedFiles([])}
                                    disabled={selectedFiles.length === 0}
                                >
                                    Clear selection
                                </Button>
                            </div>
                            <input
                                ref={folderInputRef}
                                type="file"
                                multiple
                                style={{ display: 'none' }}
                                onChange={handleFolderSelection}
                                {...({ webkitdirectory: '', directory: '' } as React.InputHTMLAttributes<HTMLInputElement>)}
                            />
                            <div {...getRootProps()} style={{ border: '1px dashed #ccc', padding: '1rem', borderRadius: '8px' }}>
                                <input {...getInputProps()} />
                                {
                                    isDragActive ?
                                    <p>Drop the DICOM folder here ...</p> :
                                    <p>Drag and drop a DICOM folder here</p>
                                }
                            </div>
                        </>
                    ) : (
                        <div {...getRootProps()}>
                            <input {...getInputProps()} />
                            {
                                isDragActive ?
                                <p>Drop the files here ...</p> :
                                <p>Drag and drop some files here, or click to select files</p>
                            }
                        </div>
                    )}
                    <div className="mt-3">
                        <h5>
                            {caller === 'CT'
                                ? `Selected DICOM files (${selectedFiles.length})`
                                : `Selected files (${selectedFiles.length})`}
                        </h5>
                        {selectedFiles.length === 0 ? (
                            <p className="text-muted mb-0">No files selected yet.</p>
                        ) : (
                            Object.entries(groupedFiles).map(([folder, files]) => (
                                <div key={folder} className="mb-2">
                                    <strong>{folder}</strong>
                                    <ul className="mb-0">
                                        {files.slice(0, 5).map((file, index) => (
                                            <li key={`${folder}-${index}`}>{file.name}</li>
                                        ))}
                                        {files.length > 5 && (
                                            <li>...and {files.length - 5} more files</li>
                                        )}
                                    </ul>
                                </div>
                            ))
                        )}
                    </div>
                </Modal.Body>
                <Modal.Footer>
                    <Button onClick={handleFileUpload} disabled={selectedFiles.length === 0}>
                        Upload
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
}

export default FileUploadDialog;
