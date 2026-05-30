import express from 'express';
import multer from 'multer';
import fs from 'fs';
import path from 'path';
import { exec } from 'child_process';
const router = express.Router();

const STATIC_ROOT = process.env.STATIC_DATA_PATH || '/app/static';
const PDF_EXTRACTOR = process.env.PDF_EXTRACTOR_PATH || '/app/scripts/pdf_extractor.py';
const DICOM_CONVERTER = process.env.DICOM_CONVERTER_PATH || '/app/scripts/dicom_converter.py';

function normalizeRelativePath(filePath: string): string {
  return filePath.replace(/\\/g, '/').replace(/^\/+/, '');
}

const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    const cnp = req.body.cnp;

    if (req.body.uploadType === 'PDF') {
      const dir = path.join(STATIC_ROOT, 'pdfs', cnp);
      fs.mkdir(dir, { recursive: true }, (error) => cb(error, dir));
      return;
    }

    const relativePath = normalizeRelativePath(file.originalname);
    const dir = path.join(STATIC_ROOT, cnp, 'dcms', path.dirname(relativePath));
    fs.mkdir(dir, { recursive: true }, (error) => cb(error, dir));
  },
  filename: function (req, file, cb) {
    if (req.body.uploadType === 'PDF') {
      cb(null, `${Date.now()}${path.extname(file.originalname)}`);
      return;
    }

    const relativePath = normalizeRelativePath(file.originalname);
    cb(null, path.basename(relativePath));
  },
});

const upload = multer({
  storage,
  limits: {
    files: 5000,
    fileSize: 1024 * 1024 * 500,
  },
}).array('file');

function runProcessing(command: string, label: string) {
  exec(command, { env: process.env, maxBuffer: 1024 * 1024 * 50 }, (error, stdout, stderr) => {
    if (stdout) {
      console.log(`[${label}] ${stdout}`);
    }
    if (stderr) {
      console.error(`[${label}] ${stderr}`);
    }
    if (error) {
      console.error(`[${label}] failed:`, error.message);
    }
  });
}

router.post('/', (req, res) => {
  upload(req, res, async (err) => {
    if (err) {
      console.error(err);
      res.status(500).send('An error occurred while uploading the file');
      return;
    }

    try {
      const cnp = req.body.cnp;

      if (req.body.uploadType === 'PDF') {
        const files = req.files as Express.Multer.File[] | undefined;
        if (!files?.length) {
          res.status(400).send('No PDF file uploaded');
          return;
        }

        for (const uploadedFile of files) {
          runProcessing(
            `python3 ${PDF_EXTRACTOR} ${cnp} ${uploadedFile.path}`,
            'pdf-extractor'
          );
        }
        res.send(
          'PDF uploaded successfully! Extraction and MongoDB sync have started.'
        );
        return;
      }

      if (req.body.uploadType === 'CT') {
        const files = req.files as Express.Multer.File[] | undefined;
        if (!files?.length) {
          res.status(400).send('No DICOM files uploaded');
          return;
        }

        const scanFolders = new Set(
          files.map((uploadedFile) => {
            const relativePath = normalizeRelativePath(uploadedFile.originalname);
            const folder = path.dirname(relativePath);
            return folder === '.' ? '(root)' : folder;
          })
        );

        console.log(
          `[ct-upload] Stored ${files.length} DICOM file(s) for CNP ${cnp} in ${Array.from(scanFolders).join(', ')}`
        );

        runProcessing(`python3 ${DICOM_CONVERTER} ${cnp}`, 'dicom-converter');
        res.send(
          'CT uploaded successfully! Conversion and feature extraction have started.'
        );
        return;
      }

      res.status(400).send('Unsupported upload type');
    } catch (error) {
      console.error(error);
      res.status(500).send('Upload processing failed');
    }
  });
});

export default router;
