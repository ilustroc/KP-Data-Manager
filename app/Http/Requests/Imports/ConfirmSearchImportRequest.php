<?php

namespace App\Http\Requests\Imports;

use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;

class ConfirmSearchImportRequest extends FormRequest
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
            'token' => ['required', 'uuid'],
            'mapping' => ['required', 'array'],
            'mapping.*' => ['required', 'string', 'max:255'],
            'confirmacion' => ['accepted'],
        ];
    }

    /** @return array<string, string> */
    public function messages(): array
    {
        return [
            'mapping.*.required' => 'Cada campo canónico debe tener una columna de origen.',
            'confirmacion.accepted' => 'Confirma explícitamente el mapping antes de registrar el batch.',
        ];
    }
}
