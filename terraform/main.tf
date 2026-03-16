resource "aws_s3_bucket" "eventhub_images" {
  bucket = "uni-istatp"
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_security_group" "eventhub_sg" {
  name        = "eventhub_web_ssh"
  description = "Allow SSH and HTTP inbound traffic"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_eip" "istatp_eip" {
  id = "eipalloc-05e8c0e7c7f4a72ce"
}

data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd*/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] # Canonical
}

resource "aws_instance" "istatp_instance" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  vpc_security_group_ids = [aws_security_group.eventhub_sg.id]
  key_name               = var.key_name
  availability_zone = var.data_volume_az

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 8
    delete_on_termination = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    app_dir    = var.app_dir
    data_device = "/dev/xvdf" # the device name used in ebs_attachment below
  })

  tags = merge(var.tags, { Name = "eventhub" })

  lifecycle {
    ignore_changes = [ami] 
  }
}

resource "aws_eip_association" "eip_assoc" {
  instance_id   = aws_instance.istatp_instance.id
  allocation_id = data.aws_eip.istatp_eip.id
}
