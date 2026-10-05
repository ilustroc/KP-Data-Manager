<?php

namespace App\Http\Requests\Payments;

use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;

class PaymentDocumentRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return $this->user()?->can('operate') ?? false;
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        return [
            'documento' => ['required', 'string', 'max:30'],
            'motivo' => ['required', 'string', 'max:260'],
        ];
    }

    /**
     * @return array<string, string>
     */
    public function messages(): array
    {
        return [
            'documento.required' => 'Ingresa el documento que se asociará al pago.',
            'documento.string' => 'El documento debe ser texto.',
            'documento.max' => 'El documento no puede exceder 30 caracteres.',
            'motivo.required' => 'Ingresa el motivo de la identificación o corrección.',
            'motivo.string' => 'El motivo debe ser texto.',
            'motivo.max' => 'El motivo no puede exceder 260 caracteres.',
        ];
    }

    protected function prepareForValidation(): void
    {
        $document = $this->input('documento');
        $reason = $this->input('motivo');

        $this->merge([
            'documento' => is_string($document) ? trim($document) : $document,
            'motivo' => is_string($reason) ? trim($reason) : $reason,
        ]);
    }
}
