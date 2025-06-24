variable "eks_oidc_provider_url" {
  description = "EKS OIDC provider URL"
  type        = string
}

variable "eks_oidc_provider_arn" {
  description = "EKS OIDC provider ARN"
  type        = string
}

variable "eks_cluster_name" {
  description = "EKS cluster name"
  type        = string
}

variable "eks_node_role_arn" {
  description = "IAM role ARN for EKS node group"
  type        = string
}

variable "eks_subnet_ids" {
  description = "List of subnet IDs for EKS node group"
  type        = list(string)
}

variable "eks_node_desired_size" {
  description = "Desired node count for spot node group"
  type        = number
  default     = 2
}

variable "eks_node_max_size" {
  description = "Max node count for spot node group"
  type        = number
  default     = 6
}

variable "eks_node_min_size" {
  description = "Min node count for spot node group"
  type        = number
  default     = 2
}

variable "eks_node_instance_types" {
  description = "List of instance types for spot node group"
  type        = list(string)
  default     = ["m5a.large", "m5.large"]
}

variable "eks_node_ondemand_instance_type" {
  description = "Instance type for on-demand node group"
  type        = string
  default     = "m5.large"
} 