"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const dotenv_1 = __importDefault(require("dotenv"));
dotenv_1.default.config();
const app = (0, express_1.default)();
const port = process.env.PORT || 3001;
const ML_ENGINE_URL = process.env.ML_ENGINE_URL || 'http://localhost:8000';
app.use((0, cors_1.default)());
app.use(express_1.default.json());
app.get('/health', (req, res) => {
    res.json({ status: 'API Gateway is running' });
});
app.post('/api/allocate', (req, res) => __awaiter(void 0, void 0, void 0, function* () {
    try {
        const { risk_capacity, selected_industries } = req.body;
        // Instead of using axios, we use native fetch to call the ML Engine
        const mlResponse = yield fetch(`${ML_ENGINE_URL}/allocate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ risk_capacity, selected_industries })
        });
        if (!mlResponse.ok) {
            throw new Error(`ML Engine answered with status ${mlResponse.status}`);
        }
        const data = yield mlResponse.json();
        res.json(data);
    }
    catch (error) {
        console.error('Error calling ML Engine:', error.message);
        res.status(500).json({ error: 'Failed to process portfolio allocation' });
    }
}));
app.listen(port, () => {
    console.log(`API Gateway listening at http://localhost:${port}`);
});
